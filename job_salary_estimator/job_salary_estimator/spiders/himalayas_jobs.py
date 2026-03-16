import scrapy
from scrapy.exceptions import CloseSpider


class HimalayasJobsSpider(scrapy.Spider):
    name = "himalayas_jobs_1500"
    allowed_domains = ["himalayas.app"]

    TARGET_ITEMS = 5000 # no jobs
    LIMIT = 20 # matches the API’s max limit

    # safety stop if the API starts returning empty
    MAX_EMPTY_PAGES = 5

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "RETRY_TIMES": 10,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 522, 524, 408],
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        },
        "FEED_EXPORT_ENCODING": "utf-8",
        # "LOG_LEVEL": "INFO",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.offset = 0
        self.items_with_salary = 0
        self.seen_guids = set()
        self.empty_pages_in_a_row = 0

    async def start(self):
        url = self._make_url(self.offset)
        yield scrapy.Request(url, callback=self.parse_api, dont_filter=True)

    def _make_url(self, offset: int) -> str:
        return f"https://himalayas.app/jobs/api?limit={self.LIMIT}&offset={offset}"

    def _extract_list(self, payload):
        """
        API-ul ar trebui sa fie o lista, dar uneori poate veni ca dict:
        {jobs:[...]}, {data:[...]}, {results:[...]} sau {error:...}
        """
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            for key in ("jobs", "data", "results"):
                if key in payload and isinstance(payload[key], list):
                    return payload[key]

            # daca e dict dar nu contine lista, probabil e error / mesaj
            snippet = str(payload)[:200]
            self.logger.warning(f"Payload dict fara lista (snippet): {snippet}")
            return None

        # alt tip
        self.logger.warning(f"Payload tip neasteptat: {type(payload)}")
        return None

    def parse_api(self, response):
        # Debug util daca iar primesti ceva ciudat
        ctype = response.headers.get("Content-Type", b"").decode("utf-8", "ignore")
        if "application/json" not in ctype:
            self.logger.warning(f"Content-Type neasteptat: {ctype}. Snippet: {response.text[:200]!r}")

        try:
            payload = response.json()
        except Exception:
            self.logger.error(f"Nu pot parsa JSON. Snippet: {response.text[:200]!r}")
            raise CloseSpider("bad_json")

        jobs = self._extract_list(payload)
        if jobs is None:
            # format neasteptat (ex: error). incercam sa avansam un pic, poate e edge/caching.
            self.empty_pages_in_a_row += 1
            if self.empty_pages_in_a_row >= self.MAX_EMPTY_PAGES:
                raise CloseSpider("bad_payload_repeated")
            self.offset += self.LIMIT
            yield scrapy.Request(self._make_url(self.offset), callback=self.parse_api, dont_filter=True)
            return

        if len(jobs) == 0:
            self.empty_pages_in_a_row += 1
            if self.empty_pages_in_a_row >= self.MAX_EMPTY_PAGES:
                raise CloseSpider("no_more_results")
            self.offset += self.LIMIT
            yield scrapy.Request(self._make_url(self.offset), callback=self.parse_api, dont_filter=True)
            return

        # avem rezultate -> reset counter
        self.empty_pages_in_a_row = 0

        for job in jobs:
            guid = job.get("guid")
            if not guid or guid in self.seen_guids:
                continue
            self.seen_guids.add(guid)

            min_salary = job.get("minSalary")
            max_salary = job.get("maxSalary")
            currency = job.get("currency")

            # keep jobs with salary
            if currency and (min_salary is not None or max_salary is not None):
                yield {
                    "source": "himalayas",
                    "guid": guid,
                    "title": job.get("title"),
                    "company": job.get("companyName"),
                    "employment_type": job.get("employmentType"),
                    "seniority": "|".join(job.get("seniority") or []),
                    "category": "|".join(job.get("category") or []),
                    "parent_categories": "|".join(job.get("parentCategories") or []),
                    "location_restrictions": "|".join(job.get("locationRestrictions") or []),
                    "timezone_restrictions": "|".join([str(x) for x in (job.get("timezoneRestrictions") or [])]),
                    "salary_currency": currency,
                    "salary_min": min_salary,
                    "salary_max": max_salary,
                    "pub_date": job.get("pubDate"),
                    "expiry_date": job.get("expiryDate"),
                    "application_link": job.get("applicationLink"),
                }

                self.items_with_salary += 1
                if self.items_with_salary >= self.TARGET_ITEMS:
                    raise CloseSpider(f"reached_target_{self.TARGET_ITEMS}")

        # next page
        self.offset += self.LIMIT
        yield scrapy.Request(self._make_url(self.offset), callback=self.parse_api, dont_filter=True)