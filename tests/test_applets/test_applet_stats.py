import asyncio
from bbot_server.modules.targets.targets_models import CreateTarget


async def test_applet_stats(bbot_server, bbot_events):
    bbot_server = await bbot_server(needs_watchdog=True)

    target1 = CreateTarget(
        target=["evilcorp.com"],
        blacklist=["www.evilcorp.com"],
    )
    target1 = await bbot_server.create_target(target1)

    # ingest BBOT events
    for scan_events in bbot_events:
        for e in scan_events:
            await bbot_server.insert_event(e)

    for _ in range(15):
        # global stats
        global_stats = await bbot_server.get_stats()
        expected_global_stats = {
            "dns_links": {
                "A": 13,
                "AAAA": 1,
                "CNAME": 1,
                "TXT": 8,
            },
            "open_ports": {
                "80": 3,
                "443": 3,
            },
            "technologies": {
                "cpe:/a:apache:http_server:2.4.12": 2,
                "cpe:/a:microsoft:internet_information_services": 1,
            },
            # "cloud_providers": {
            #     "Azure": 1,
            #     "Amazon": 2,
            # },
            "findings": {
                "max_severity": "CRITICAL",
                "max_severity_score": 5,
                "names": {
                    "CVE-2024-12345": 2,
                    "CVE-2025-54321": 2,
                },
                "severities": {
                    "CRITICAL": 2,
                    "HIGH": 2,
                },
                "counts_by_host": {
                    "www.evilcorp.com": 1,
                    "www2.evilcorp.com": 2,
                    "api.evilcorp.com": 1,
                },
                "severities_by_host": {
                    "www.evilcorp.com": {
                        "max_severity": "HIGH",
                        "max_severity_score": 4,
                    },
                    "www2.evilcorp.com": {
                        "max_severity": "CRITICAL",
                        "max_severity_score": 5,
                    },
                    "api.evilcorp.com": {
                        "max_severity": "CRITICAL",
                        "max_severity_score": 5,
                    },
                },
            },
        }
        global_stats_ok = global_stats == expected_global_stats

        # by target
        stats_by_target = await bbot_server.get_stats(target_id=target1.id)
        expected_stats_by_target = {
            "dns_links": {
                "A": 9,
                "CNAME": 1,
                "TXT": 8,
            },
            "open_ports": {
                "80": 2,
                "443": 3,
            },
            "technologies": {
                "cpe:/a:apache:http_server:2.4.12": 2,
                "cpe:/a:microsoft:internet_information_services": 1,
            },
            # "cloud_providers": {
            #     "Amazon": 1,
            # },
            "findings": {
                "max_severity": "CRITICAL",
                "max_severity_score": 5,
                "names": {
                    "CVE-2024-12345": 1,
                    "CVE-2025-54321": 2,
                },
                "severities": {
                    "CRITICAL": 2,
                    "HIGH": 1,
                },
                "counts_by_host": {
                    "api.evilcorp.com": 1,
                    "www2.evilcorp.com": 2,
                },
                "severities_by_host": {
                    "api.evilcorp.com": {
                        "max_severity": "CRITICAL",
                        "max_severity_score": 5,
                    },
                    "www2.evilcorp.com": {
                        "max_severity": "CRITICAL",
                        "max_severity_score": 5,
                    },
                },
            },
        }
        stats_by_target_ok = stats_by_target == expected_stats_by_target

        # by domain
        stats_by_domain = await bbot_server.get_stats(domain="www2.evilcorp.com")
        expected_stats_by_domain = {
            "dns_links": {
                "A": 2,
            },
            "open_ports": {
                "80": 1,
            },
            "technologies": {},
            # "cloud_providers": {},
            "findings": {
                "max_severity": "CRITICAL",
                "max_severity_score": 5,
                "names": {
                    "CVE-2024-12345": 1,
                    "CVE-2025-54321": 1,
                },
                "severities": {
                    "CRITICAL": 1,
                    "HIGH": 1,
                },
                "counts_by_host": {
                    "www2.evilcorp.com": 2,
                },
                "severities_by_host": {
                    "www2.evilcorp.com": {
                        "max_severity": "CRITICAL",
                        "max_severity_score": 5,
                    },
                },
            },
        }
        stats_by_domain_ok = stats_by_domain == expected_stats_by_domain

        if global_stats_ok and stats_by_target_ok and stats_by_domain_ok:
            break

        await asyncio.sleep(0.5)

    assert global_stats == expected_global_stats
    assert stats_by_target == expected_stats_by_target
    assert stats_by_domain == expected_stats_by_domain
