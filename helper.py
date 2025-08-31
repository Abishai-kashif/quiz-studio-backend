import urllib.parse

class Helper:
    @staticmethod
    def is_url(text: str) -> bool:
        """
        Returns true if the provided text is a url, false otherwise.
        """
        parsed = urllib.parse.urlparse(text)
        return bool(parsed.netloc) and bool(parsed.scheme)
    

if __name__ == "__main__":
    assert Helper.is_url("https://www.google.com") is True
    