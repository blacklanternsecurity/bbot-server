def make_httpx_response(target, input=None, port=0, body="") -> str:
    if input is None:
        input = str(target)
    if not target.startswith("http"):
        target = f"https://{target}"
    httpx_response = r"""{"status_code":200,"timestamp":"2024-06-21T12:55:46.154206378-04:00","hash":{"body_md5":"6ff3d946fb246e51fef52e59080feca0","body_mmh3":"-159699765","body_sha256":"21c2d35e468a03e7b663d81a8f0317e56d090d3eeb356f4fadda5a5f9e30753f","body_simhash":"15672521343079506636","header_md5":"d812fb508413c41a7912dd50b143e6a4","header_mmh3":"-509086190","header_sha256":"f6e451ea71e71af21fb1de94c4d6ff73bc8656647431a98063f16218f967be2c","header_simhash":"9832066127707744238"},"port":"<port>","url":"<target>","input":"<input>","scheme":"https","webserver":"cloudflare","body":"<body>","content_type":"text/plain","method":"GET","host":"104.16.185.241","path":"/","header":{}}"""
    httpx_response = httpx_response.replace("<target>", target)
    httpx_response = httpx_response.replace("<input>", input)
    httpx_response = httpx_response.replace("<port>", str(port))
    httpx_response = httpx_response.replace("<body>", body)
    return httpx_response
