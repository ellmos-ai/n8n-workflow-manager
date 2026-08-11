# Third-party licenses

This project ships third-party code inside the repository and inside the built
distributions. The repository [`LICENSE`](LICENSE) (MIT, Copyright (c) 2026 Lukas
Geiger) covers **only the code written for this project**. The components listed
below keep their own licenses and copyright holders.

---

## vis-network 10.1.0

- **Bundled file:** `n8nManager/web/static/js/vis-network.min.js`
- **Upstream:** <https://visjs.github.io/vis-network/>
- **Version:** 10.1.0 (pinned; SHA-256 verified against the upstream
  distribution, see `tests/test_hardening.py`)
- **Why it is bundled:** the browser graph viewer must work without a CDN so the
  application stays local-first and can run fully offline under a strict
  Content-Security-Policy.

vis-network is distributed under a **dual license**: Apache License 2.0 **or**
the MIT License, at the recipient's option.

**Option exercised by this project: the MIT License.** The full text of that
license as it applies to vis-network follows.

```
Copyright (c) 2011-2017 Almende B.V, http://almende.com
Copyright (c) 2017-2019 visjs contributors, https://github.com/visjs

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Choosing the MIT option does not remove the Apache-2.0 option for anyone else:
downstream recipients may still take vis-network under Apache-2.0 directly from
upstream.

---

## Runtime dependencies

Packages declared in `pyproject.toml` (FastAPI, Uvicorn, httpx, Jinja2,
Pydantic, python-multipart, and the optional `paramiko`) are **not** vendored.
They are installed by pip from PyPI and remain under their own licenses; consult
the installed distributions for their notices.

---

## Trademarks

"n8n" is a trademark of its respective owner. This project is an independent
community tool and is neither affiliated with, endorsed by, nor sponsored by
n8n GmbH. The name is used to describe what the software interoperates with.
See the trademark notice in [`README.md`](README.md).
