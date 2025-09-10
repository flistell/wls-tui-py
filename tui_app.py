from os import link
from urllib.parse import urlparse
from textual.app import App, ComposeResult
from rich.text import Text
from textual.widgets import  Header, Footer, Input, Pretty, Tree, TextArea, TabbedContent, TabPane
from textual.containers import Horizontal
from textual.reactive import reactive
from textual import on
from rich.highlighter import ReprHighlighter
import requests
import json
import logging

class LocationBar(Input):
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
        self.add_links_node(links)

    def add_links_node(self, links, parent_node=None):
        # Sort links by 'rel'
        logging.debug(f"Adding links to tree panel: {repr(links)}")
        sorted_links = sorted(links, key=lambda x: x.get('rel', '').casefold())
        if parent_node is None:
            # Initial population
            self.clear()
            parent = self.root.add('parent', expand=True)
            parent.allow_expand = True
            current = parent.add_leaf('self')
            current.allow_expand = True
            for link in sorted_links:
                if link['rel'] in ['parent']:
                    parent.data = link
                    href_parsed = urlparse(link['href'])
                    parent.label = href_parsed.path.split('/')[-1] 
                if link['rel'] in ['self']:
                    current.data = link
                    href_parsed = urlparse(link['href'])
                    current.label = href_parsed.path.split('/')[-1]
                if link['rel'] not in ['parent', 'self', 'canonical']:
                    logging.debug(f"Adding link to tree: {link['rel']}")
                    node = current.add_leaf(link['rel'])
                    node.data = link  # Store the link dict for later access
            self.root.expand_all()
        else:
            # Only add children if not already added
            if parent_node.children:
                logging.debug(f"Node {parent_node.label} already has children, skipping add_node.")
                return
            for link in sorted_links:
                if link['rel'] not in ['parent', 'self', 'canonical']:
                    logging.debug(f"Adding link under selected node: {link['rel']}")
                    if link['rel'] == 'action' and 'title' in link:
                        node = parent_node.add_leaf(f"{link['rel']} ({link['title']})")
                    else:
                        node = parent_node.add_leaf(link['rel'])
                    node.data = link
                    parent_node.allow_expand = True

class OutputPanelArea(TextArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_only = True

    def update_output(self, data):
        self.text = (json.dumps(data, indent=2))


class OutputPanelTree(Tree):
    def __init__(self, *args, **kwargs):
        super().__init__("Output", *args, **kwargs)
        self.update_output({})

    def update_output(self, data):
        self.clear()
        self.add_json(data)
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

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("shift+right", "expand_node", "Expand"),
        ("shift+left", "collapse_node", "Collapse"),
        ("l", "expand_node", "Expand"),
        ("h", "collapse_node", "Collapse"),
        ("t", "show_tab('text')", "Text View"),
        ("y", "show_tab('json')", "JSON View")
    ]

    uri = reactive("")
    links = reactive([])
    output = reactive({})
    output_mode = 'text' # can be 'text' or 'json'
    data = None

    unclutter = True

    def __init__(self, start_uri, auth=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uri = start_uri
        self.auth = auth
        self.highlighter = ReprHighlighter()

    def compose(self) -> ComposeResult:
        self.breadcrumb = LocationBar(f"URI: {self.uri}", id="locationbar")
        self.tree_panel = TreePanel([], id='treepanel')
        self.output_text = OutputPanelArea(id='output_text')
        self.output_json = OutputPanelTree(id='output_json')
        yield Header()
        yield Footer()
        yield self.breadcrumb
        with Horizontal():
            yield self.tree_panel
            with TabbedContent(id="container", initial="text"):
                with TabPane("Text", id="text"):
                    yield self.output_text
                with TabPane("Json", id="json"):
                    yield self.output_json

    def setUnclutter(self, unclutter):
        self.unclutter = unclutter

    def on_mount(self):
        self.fetch_and_update(self.uri)

    def fetch_and_update(self, uri, current_node=None):
        try:
            # Fetch JSON data
            logging.info(f"Fetching and update URI: {uri}")
            resp = requests.get(uri, auth=self.auth, verify=False)
            resp.raise_for_status()
            data = resp.json()
            logging.debug(f"Fetched data: {data}")

            # Update UI Components
            logging.debug("Update breadcrumb.")
            self.breadcrumb.update_uri(uri)
            logging.debug("Update links panel.")
            if current_node is None:
                self.tree_panel.add_links_node(data.get('links', []))
            else:
                #
                #  + node
                #     + 'items'
                #
                if 'items' in data:
                    logging.debug("Adding sub-item links to tree panel.")
                    for data_i in data['items']:
                        logging.debug(f"Adding 'item' to tree: {data_i}")
                        if 'links' in data_i:
                            for link in data_i.get('links'):
                                if link['rel'] == 'canonical':
                                    links_item = {
                                        'rel': data_i.get('name','item'),
                                        'href': link['href']
                                    }
                                    data['links'].append(links_item)
                    current_node.allow_expand = True
                    current_node.expand()
                if 'links' in data:
                    self.tree_panel.add_links_node(data['links'], current_node)
            logging.debug("Update output.")
            if self.unclutter:
                data.pop('links', None)  # Remove links from output display
            self.data = data
            self.output_text.update_output(data)
            self.output_json.update_output(data)
            logging.info(f"Fetched and updated panels for URI: {uri}")
        except Exception as e:
            logging.error(f"Error fetching URI {uri}: {e}")
            data = f'"error": "{str(e)}"'
            self.data = data
            self.output_text.update_output(data)
            self.output_json.update_output(data)

    def action_show_tab(self, tab: str) -> None:
        self.query_one(TabbedContent).active = tab

    def action_cursor_up(self):
        self.tree_panel.action_cursor_up()

    def action_cursor_down(self):
        self.tree_panel.action_cursor_down()

    def action_cursor_parent(self):
        node = self.tree_panel.cursor_node
        if node and node.parent:
            self.tree_panel.move_cursor(node.parent)

    def action_expand_node(self):
        logging.debug("Expand node action triggered.")
        node = self.tree_panel.cursor_node
        if node:
            node.expand()

    def action_collapse_node(self):
        logging.debug("Collapse node action triggered.")
        node = self.tree_panel.cursor_node
        if node:
            node.collapse()

    @on(Tree.NodeSelected)
    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        logging.debug(f"Tree node selected event: {node}, {node.data}")
        if node and node.data and "href" in node.data:
            node_uri = node.data["href"]
            self.fetch_and_update(node_uri, current_node=node)

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.uri = event.value
        self.value = event.value
        self.fetch_and_update(event.value)



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
    parser.add_argument("--clutter", help="Show full JSON data than can clutter the output")
    parser.add_argument("--log", default="INFO", help="Logging level (default: INFO)")
    args, unknown = parser.parse_known_args()

    username = args.username or os.getenv("WLS_USERNAME")
    password = args.password or os.getenv("WLS_PASSWORD")
    unclutter = False if args.clutter else True

    auth = (username, password) if username and password else None
    uri = None
    if not unknown or len(unknown) < 1:
        uri = os.getenv("WLS_URI") 
    if not uri:
        uri = "http://127.0.0.1:7001"
    logging.basicConfig(
        filename="tui_app.log",
        level=args.log.upper(),
        format="%(asctime)s %(levelname)s: %(message)s"
    )
    
    app = TuiApp(uri + '/management/weblogic/latest', auth)
    app.run()
