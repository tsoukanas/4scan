import webbrowser
import fourscan

def open_thread(post, scan):
    url = post.semantic_url
    webbrowser.open(url)

scanner = fourscan.scan_forever(callback=open_thread)
