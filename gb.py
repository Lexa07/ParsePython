import typing
import requests
from urllib.parse import urljoin
import bs4
import time
import pymongo
import time

class GbBlogParse:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintoch; Intel Mac 05 X 10.15; rv:88.0"
                        "Gesko/20100101 Firefox/88.0"
    }
    __parse_time = 1

    def __init__(self, start_url, db, delay=1.0):
        self.start_url = start_url
        self.db = db
        self.delay = delay
        self.done_url: typing.Set[str] = set()
        self.task: typing.List[typing.Callable] = [self.get_task(self.start_url, self.parse_feed)]
        self.done_url.add(self.start_url)


    def _get_response(self, url):
        while True:
            next_time = self.__parse_time + self.delay
            if next_time > time.time():
                time.sleep(next_time - time.time())
            response = requests.get(url, headers=self.headers)
            print(f"RESPONSE: {response.url}")
            self.__parse_time = time.time()
            if response.status_code == 200:
                return response

    def get_task(self, url: str, callback: typing.Callable) -> typing.Callable:
        def task():
            response = self._get_response(url)
            return callback(response)

        return task

    def run(self):
        while True:
            try:
                task = self.task.pop(0)
                task()
            except IndexError:
                break


    def task_creator(self, urls: set, callback):
        urls_set = urls - self.done_url
        for url in urls_set:
            self.task.append(self.get_task(url, callback))
            self.done_url.add(url)



    def parse_feed(self, response: requests.Response):
        soup = bs4.BeautifulSoup(response.text, "lxml")
        ul_pagin = soup.find("ul", attrs={"class": "gb__pagination"})
        self.task_creator(
            {urljoin(response.url, a_tag.attrs["href"])
             for a_tag in ul_pagin.find_all("a") if a_tag.attrs.get("href")},
            self.parse_feed,
        )
        post_wrapper = soup.find("div", attrs={"class": "post-items-wrapper"})
        self.task_creator(
            {urljoin(response.url, a_tag.attrs["href"])
             for a_tag in post_wrapper.find_all("a", attrs={"class": "post-item__title"})
             if a_tag.attrs.get("href")},
            self.parse_post
        )


    def parse_post(self, response: requests.Response):
        soup = bs4.BeautifulSoup(response.text, "lxml")
        author_name_tag = soup.find("div", itemprop="author")
        data = {
            "url": response.url,
            "title": soup.find("h1", attrs={"class": "blogpost-title"}).text,
            "author": {
                "url": urljoin(response.url, author_name_tag.parent.attrs.get("href")),
                "name": author_name_tag.text,
                },
        }
        self._save(data)

    def _save(self, data):
        collection = self.db["gbParse30_05_2021"]["gbParse"]
        collection.insert_one(data)


if __name__ == '__main__':
    db_client = pymongo.MongoClient()
    parser = GbBlogParse("https://gb.ru/posts", db_client, 0.5)
    parser.run()

