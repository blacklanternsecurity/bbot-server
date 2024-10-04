base_dns_mock = {
    "blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
        "TXT": ["www.blacklanternsecurity.com", "asdf.blacklanternsecurity.com", "api.blacklanternsecurity.com"],
    },
    "www.blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
    },
}

dns_mock_1 = dict(base_dns_mock)
dns_mock_1.update(
    {
        "asdf.blacklanternsecurity.com": {
            "A": ["127.0.0.1"],
        }
    }
)

dns_mock_2 = dict(base_dns_mock)
dns_mock_2.update(
    {
        "api.blacklanternsecurity.com": {
            "A": ["127.0.0.1"],
        }
    }
)


scan1_events = None
scan2_events = None


def patch_scan(self, scan):

    old_run_live = scan.helpers.run_live

    async def new_run_live(*command, check=False, text=True, **kwargs):
        if command and isinstance(command[0], list) and command[0][0] == "httpx":
            _input = [l for l in kwargs["input"]]
            if "blacklanternsecurity.com:443" in _input:
                yield r"""{"timestamp":"2024-06-21T12:55:46.154206378-04:00","hash":{"body_md5":"6ff3d946fb246e51fef52e59080feca0","body_mmh3":"-159699765","body_sha256":"21c2d35e468a03e7b663d81a8f0317e56d090d3eeb356f4fadda5a5f9e30753f","body_simhash":"15672521343079506636","header_md5":"d812fb508413c41a7912dd50b143e6a4","header_mmh3":"-509086190","header_sha256":"f6e451ea71e71af21fb1de94c4d6ff73bc8656647431a98063f16218f967be2c","header_simhash":"9832066127707744238"},"port":"443","url":"https://blacklanternsecurity.com:443","input":"blacklanternsecurity.com:443","scheme":"https","webserver":"cloudflare","body":"96.65.132.137\n","content_type":"text/plain","method":"GET","host":"104.16.185.241","path":"/","header":{"access_control_allow_methods":"GET","access_control_allow_origin":"*","alt_svc":"h3=\":443\"; ma=86400","cf_ray":"897587313c7353b7-ATL","content_length":"14","content_type":"text/plain","date":"Fri, 21 Jun 2024 16:55:46 GMT","server":"cloudflare","set_cookie":"__cf_bm=PJp0Q02xhccvFmCx2e5eKUcq.TLWztkrvqEmwdIu9Cg-1718988946-1.0.1.1-qggK_.d8LqVpZknBI19PBvvhoaQRBTsv6KHCJubvp.lNQ14aakLf8Xu2lmWHGuKN2NjMDAh2Y8jctZuoo9T7Ig; path=/; expires=Fri, 21-Jun-24 17:25:46 GMT; domain=.blacklanternsecurity.com; HttpOnly; Secure; SameSite=None","vary":"Accept-Encoding"},"raw_header":"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 14\r\nAccess-Control-Allow-Methods: GET\r\nAccess-Control-Allow-Origin: *\r\nAlt-Svc: h3=\":443\"; ma=86400\r\nCf-Ray: 897587313c7353b7-ATL\r\nContent-Type: text/plain\r\nDate: Fri, 21 Jun 2024 16:55:46 GMT\r\nServer: cloudflare\r\nSet-Cookie: __cf_bm=PJp0Q02xhccvFmCx2e5eKUcq.TLWztkrvqEmwdIu9Cg-1718988946-1.0.1.1-qggK_.d8LqVpZknBI19PBvvhoaQRBTsv6KHCJubvp.lNQ14aakLf8Xu2lmWHGuKN2NjMDAh2Y8jctZuoo9T7Ig; path=/; expires=Fri, 21-Jun-24 17:25:46 GMT; domain=.blacklanternsecurity.com; HttpOnly; Secure; SameSite=None\r\nVary: Accept-Encoding\r\n\r\n","request":"GET / HTTP/1.1\r\nHost: blacklanternsecurity.com\r\nUser-Agent: Mozilla/5.0 (Linux; Android 10; Redmi Note 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.101 Mobile Safari/537.36\r\nAccept-Charset: utf-8\r\nAccept-Encoding: gzip\r\n\r\n","time":"221.605004ms","a":["104.16.185.241","104.16.184.241","2606:4700::6810:b9f1","2606:4700::6810:b8f1"],"words":1,"lines":2,"status_code":200,"content_length":14,"failed":false}"""
        else:
            async for _ in old_run_live(*command, check=False, text=True, **kwargs):
                yield _

    self.fixtures.monkeypatch.setattr(scan.helpers, "run_live", new_run_live)


async def gen_scan_data(self):
    from pathlib import Path
    from bbot import Scanner, Preset

    bbot_preset_file = Path(__file__).parent / "bbot_preset.yml"
    bbot_preset = Preset.from_yaml_file(bbot_preset_file)

    global scan1_events
    global scan2_events

    if scan1_events is None:
        scan1 = Scanner(preset=bbot_preset)
        self.patch_scan(scan1)
        await scan1.helpers.dns._mock_dns(dns_mock_1)
        scan1_events = [e async for e in scan1.async_start()]
    self._scan1_events = scan1_events

    if scan2_events is None:
        scan2 = Scanner(preset=bbot_preset)
        self.patch_scan(scan2)
        await scan2.helpers.dns._mock_dns(dns_mock_2)
        scan2_events = [e async for e in scan2.async_start()]
    self._scan2_events = scan2_events

    return self.scan1_events, self.scan2_events
