class ObservedBlueSkyPost:

    def __init__(self, commit_repo: str, text: str, atproto_uri: str, http_url_to_post: str, profile_url: str,
                 content_identifier: str):
        self.commit_repo = commit_repo
        self.text = text
        self.atproto_uri = atproto_uri
        self.http_url_to_post = http_url_to_post
        self.profile_url = profile_url
        self.content_identifier = content_identifier