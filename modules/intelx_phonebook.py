# bbot/modules/intelx_phonebook.py

import asyncio
import json
import re
from urllib.parse import urlparse, urlencode

from bbot.modules.base import BaseModule


class intelx_phonebook(BaseModule):
    """
    BBOT module that queries IntelligenceX Phonebook API for a domain
    and emits EMAIL_ADDRESS, DNS_NAME (subdomains) and URL_UNVERIFIED events.
    """

    # Consume DNS_NAME, emit emails, subdomains and URLs (unverified)
    watched_events = ["DNS_NAME"]
    produced_events = ["EMAIL_ADDRESS", "DNS_NAME", "URL_UNVERIFIED"]

    flags = ["passive", "safe"]

    meta = {
        "description": "Query IntelligenceX Phonebook API to gather emails, "
                       "subdomains and unverified URLs for a domain",
        "author": "your-name-here",
    }

    # Module configuration options
    options = {
        "api_key": "",
        "api_url": "https://2.intelx.io",
        "buckets": [],              # [] = all buckets allowed by your key
        "maxresults": 1000,         # max selectors per search
        "result_page_size": 100,    # how many records per /result call
        "poll_interval": 1.0,       # seconds between polling /result
        "max_polls": 10,            # safety limit for polling loop
        "user_agent": "bbot-intelx-phonebook/1.0",
    }

    options_desc = {
        "api_key": "IntelligenceX API key (sent as x-key header)",
        "api_url": "Base URL for the IntelligenceX API instance",
        "buckets": "Optional list of buckets to restrict search (empty = all accessible)",
        "maxresults": "Maximum number of phonebook results to ask for (per search)",
        "result_page_size": "Limit for records per /phonebook/search/result call",
        "poll_interval": "Seconds to sleep between polling result pages",
        "max_polls": "Maximum number of polling iterations per search",
        "user_agent": "User-Agent header to send to IntelligenceX",
    }

    # Only run once per domain
    per_domain_only = True

    # -------------------- Setup --------------------

    async def setup(self):
        """
        One-time setup at scan start. Validates config and stores settings.
        Must return True (success), None (soft-fail), or False (hard-fail).
        """
        self.api_key = self.config.get("api_key")
        if not self.api_key:
            # Soft-fail if no API key is set
            return None, "IntelligenceX API key (modules.intelx_phonebook.api_key) is not set"

        self.api_url = (self.config.get("api_url") or "https://api.intelx.io").rstrip("/")
        self.buckets = self.config.get("buckets") or []
        self.maxresults = int(self.config.get("maxresults", 1000))
        self.result_page_size = int(self.config.get("result_page_size", 100))
        self.poll_interval = float(self.config.get("poll_interval", 1.0))
        self.max_polls = int(self.config.get("max_polls", 10))
        self.user_agent = self.config.get("user_agent", "bbot-intelx-phonebook/1.0")

        return True

    # -------------------- Event handler --------------------

    async def handle_event(self, event):
        """
        Called automatically for each DNS_NAME because it's in watched_events.
        """
        # Normalize to base domain (e.g., foo.bar.example.com -> example.com)
        _, domain = self.helpers.split_domain(event.data)
        if not domain:
            self.debug(f"[intelx_phonebook] Could not determine base domain from {event.data}")
            return

        self.hugeinfo(f"[intelx_phonebook] Querying IntelligenceX Phonebook for {domain}")

        search_id = await self._start_phonebook_search(domain)
        if not search_id:
            return

        try:
            await self._collect_results(search_id, event, domain)
        finally:
            # Best-effort cleanup of server-side search job
            await self._terminate_search(search_id)

    # -------------------- IntelligenceX API helpers --------------------

    def _headers(self, json_body=False):
        headers = {
            "x-key": self.api_key,           # API key header
            "User-Agent": self.user_agent,   # required by API docs
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    async def _start_phonebook_search(self, domain):
        """
        POST /phonebook/search with a JSON request.
        Returns the search ID on success.
        """
        url = f"{self.api_url}/phonebook/search"

        payload = {
            "term": domain,
            "buckets": self.buckets,
            "lookuplevel": 0,
            "maxresults": self.maxresults,
            "timeout": 0,
            "datefrom": "",
            "dateto": "",
            "sort": 2,   # xscore DESC (most relevant first)
            "media": 0,  # not used as filter in phonebook
            "terminate": [],
        }

        body = json.dumps(payload)
        try:
            response = await self.helpers.request(
                url,
                method="POST",
                data=body,
                headers=self._headers(json_body=True),
            )
        except Exception as e:
            self.error(f"[intelx_phonebook] Error starting phonebook search (network): {e}")
            return None

        # Only treat None as “no response”, not falsy status codes
        if response is None:
            self.error("[intelx_phonebook] No HTTP response from /phonebook/search (network error?)")
            return None

        status_code = getattr(response, "status", getattr(response, "status_code", ""))
        raw_text = getattr(response, "text", "")
        self.debug(f"[intelx_phonebook] /phonebook/search HTTP status: {status_code}")
        self.debug(f"[intelx_phonebook] /phonebook/search raw body (first 400 chars): {raw_text[:400]}")

        try:
            data = response.json()
        except Exception as e:
            self.error(
                f"[intelx_phonebook] Failed to parse JSON from /phonebook/search: {e}; "
                f"raw body (first 200 chars): {raw_text[:200]}"
            )
            return None

        status = data.get("status")
        if status != 0:
            self.error(f"[intelx_phonebook] Search error, status={status}, response={data}")
            return None

        search_id = data.get("id")
        if not search_id:
            self.error(f"[intelx_phonebook] No 'id' in /phonebook/search response: {data}")
            return None

        self.debug(f"[intelx_phonebook] Phonebook search started, id={search_id}")
        return search_id

    async def _collect_results(self, search_id, parent_event, root_domain):
        """
        Poll /phonebook/search/result until status indicates completion or we hit max_polls.
        """
        seen = set()
        polls = 0

        while polls < self.max_polls:
            polls += 1

            query = urlencode({
                "id": search_id,
                "limit": self.result_page_size,
            })
            url = f"{self.api_url}/phonebook/search/result?{query}"

            try:
                response = await self.helpers.request(
                    url,
                    method="GET",
                    headers=self._headers(),
                )
            except Exception as e:
                self.error(f"[intelx_phonebook] Error requesting phonebook results: {e}")
                return

            if response is None:
                self.error("[intelx_phonebook] No HTTP response from /phonebook/search/result")
                return

            raw_text = getattr(response, "text", "")

            try:
                data = response.json()
            except Exception as e:
                self.error(
                    f"[intelx_phonebook] Failed to parse JSON from /phonebook/search/result: {e}; "
                    f"raw body (first 200 chars): {raw_text[:200]}"
                )
                return

            status = data.get("status")
            # Try both 'selectors' and 'records' as possible container keys
            records = data.get("selectors") or data.get("records") or []

            if records:
                await self._process_records(records, parent_event, root_domain, seen)

            # 0 = success with results, 1 = all delivered, 3 = keep trying, 2 = ID not found
            if status == 1:
                self.debug("[intelx_phonebook] Search completed (status=1)")
                break
            elif status in (0, 3):
                await asyncio.sleep(self.poll_interval)
                continue
            else:
                self.warning(f"[intelx_phonebook] Stopping on unexpected status={status}")
                break

    async def _process_records(self, records, parent_event, root_domain, seen):
        """
        Extract selector values from phonebook records and classify as email / URL / host.
        """
        for record in records:
            # IntelligenceX phonebook JSON field name varies; try common variants.
            value = (
                record.get("selectorvalue")
                or record.get("value")
                or record.get("selector")
                or ""
            )

            if not value:
                continue

            value = value.strip()
            if not value or value in seen:
                continue
            seen.add(value)

            # Basic classification purely by syntax.
            if "@" in value:
                await self._emit_email(value, parent_event)
            elif "://" in value or value.startswith("www."):
                await self._emit_url(value, parent_event, root_domain)
            else:
                await self._emit_host(value, parent_event, root_domain)

    # -------------------- Emit helpers --------------------

    async def _emit_email(self, email, parent_event):
        email = email.lower()
        self.debug(f"[intelx_phonebook] EMAIL_ADDRESS -> {email}")
        await self.emit_event(email, "EMAIL_ADDRESS", parent=parent_event)

    async def _emit_url(self, url, parent_event, root_domain):
        # Normalize URL: if there is no scheme, assume HTTP
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
            url = "http://" + url

        self.debug(f"[intelx_phonebook] URL_UNVERIFIED -> {url}")
        await self.emit_event(url, "URL_UNVERIFIED", parent=parent_event)

        # Also emit subdomain (DNS_NAME) if the host is under the root domain
        try:
            hostname = urlparse(url).hostname
        except Exception:
            hostname = None

        if hostname:
            await self._emit_host(hostname, parent_event, root_domain)

    async def _emit_host(self, host, parent_event, root_domain):
        host = host.strip(".")
        if not host:
            return

        h_lower = host.lower()
        d_lower = root_domain.lower()

        # Only emit subdomains of the target root domain, not the root itself.
        if h_lower.endswith("." + d_lower) and h_lower != d_lower:
            self.debug(f"[intelx_phonebook] DNS_NAME -> {host}")
            await self.emit_event(host, "DNS_NAME", parent=parent_event)

    # -------------------- Cleanup --------------------

    async def _terminate_search(self, search_id):
        """
        GET /intelligent/search/terminate?id=... to free server-side resources.
        Works for both normal and phonebook searches per API docs.
        """
        query = urlencode({"id": search_id})
        url = f"{self.api_url}/intelligent/search/terminate?{query}"

        try:
            await self.helpers.request(
                url,
                method="GET",
                headers=self._headers(),
            )
        except Exception as e:
            # Not fatal; just log at debug level
            self.debug(f"[intelx_phonebook] Failed to terminate search {search_id}: {e}")

