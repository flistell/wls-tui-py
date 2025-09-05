from tkinter import Label
from textual.app import App, ComposeResult
from textual.widgets import Static, Header, Footer, Input, Pretty, Tree
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
import requests
import json
import logging

class Breadcrumb(Input):
    def __init__(self, uri, *args, **kwargs):
        super().__init__(placeholder="URI")
        self.uri = uri
        self.update_uri(uri)

    def update_uri(self, uri: str):
        self.value = uri

class TreePanel(Tree):
    def __init__(self, links, *args, **kwargs):
        super().__init__("Links", *args, **kwargs)
        self.links = links
        self.update_links(links)

    def update_links(self, links):
        self.clear()
        parent = self.root.add('parent', expand=True)
        parent.data = [x for x in links if x['rel'] == 'parent']
        current = parent.add_leaf('self')
        current.data = [x for x in links if x['rel'] == 'self']
        for link in links:
            if link['rel'] not in ['parent', 'self', 'canonical']:
                logging.debug(f"Adding link to tree: {link['rel']}")
                node = current.add_leaf(link['rel'])
                node.data = link  # Store the link dict for later access
        self.root.expand_all()

class OutputPanel(Tree):
    def __init__(self, *args, **kwargs):
        super().__init__("Output", *args, **kwargs)
        self.update_output({})

    def update_output(self, data):
        self._populate_tree(self.root, data)
        self.root.expand_all()

    def _populate_tree(self, node, value):
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, (dict, list)):
                    child = node.add(str(k))
                    self._populate_tree(child, v)
                if isinstance(v, str):  
                    child = node.add(f"{k}: {v}")
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                child = node.add(f"[{idx}]")
                self._populate_tree(child, item)
        else:
            node.add_leaf(str(value))

class TuiApp(App):
    CSS_PATH = "tui_app.tcss"

    BINDINGS = [("up", "cursor_up", "Up"), ("down", "cursor_down", "Down"),
                ("j", "cursor_down", "Down"), ("k", "cursor_up", "Up"),
                ("enter", "select_link", "Select")]

    uri = reactive("")
    links = reactive([])
    output = reactive({})

    def __init__(self, start_uri, auth=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uri = start_uri
        self.auth = auth

    def compose(self) -> ComposeResult:
        self.breadcrumb = Breadcrumb(f"URI: {self.uri}")
        self.tree_panel = TreePanel([])
        self.output_panel = OutputPanel()
        yield Header()
        yield self.breadcrumb
        with Horizontal():
            yield self.tree_panel
            yield self.output_panel
        yield Footer()

    def on_mount(self):
        self.fetch_and_update(self.uri)

    def fetch_and_update(self, uri):
        try:
            logging.info(f"Fetching and update URI: {uri}")
            resp = requests.get(uri, auth=self.auth, verify=False)
            resp.raise_for_status()
            data = resp.json()
            logging.info(f"Fetched data: {data}")
            self.output = data
            self.links = data.get("links", [])
            logging.debug("Update breadcrumb.")
            self.breadcrumb.update_uri(uri)
            logging.debug("Update links panel.")
            self.tree_panel.update_links(self.links)
            logging.debug("Update output.")
            self.output_panel.update_output(data)
            logging.info(f"Fetched and updated panels for URI: {uri}")
        except Exception as e:
            logging.error(f"Error fetching URI {uri}: {e}")
            self.output_panel.update_output({"error": str(e)})

    def action_cursor_up(self):
        self.tree_panel.action_cursor_up()

    def action_cursor_down(self):
        self.tree_panel.action_cursor_down()

    def action_select_link(self):
        node = self.tree_panel.cursor_node
        if node and node.data and "href" in node.data:
            href = node.data["href"]
            self.uri = href
            self.fetch_and_update(href)

# For manual testing:
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    import argparse
    import os

    load_dotenv()  # Load .env file if present

    parser = argparse.ArgumentParser(description="Fetch JSON from a URL with authentication (accepts insecure HTTPS).")
    parser.add_argument("--username", help="Username for authentication")
    parser.add_argument("--password", help="Password for authentication")
    parser.add_argument("--log", default="INFO", help="Logging level (default: INFO)")
    args, unknown = parser.parse_known_args()

    username = args.username or os.getenv("WLS_USERNAME")
    password = args.password or os.getenv("WLS_PASSWORD")

    auth = (username, password) if username and password else None
    uri = unknown[0] if unknown else "https://example.com/api"
    
    logging.basicConfig(
        filename="tui_app.log",
        level=args.log.upper(),
        format="%(asctime)s %(levelname)s: %(message)s"
    )
    
    app = TuiApp(uri, auth)
    app.run()
    app.run()
    app.run()
