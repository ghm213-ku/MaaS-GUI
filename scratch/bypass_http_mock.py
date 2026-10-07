import sys

file_path = "ui/main_window.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target1 = """    def fetch_booked_channels(self):
        try:
            resp = self.session.get("http://127.0.0.1:8000/api/v1/channels", timeout=2)"""
replace1 = """    def fetch_booked_channels(self):
        if getattr(self, 'force_mock', False):
            return
        try:
            resp = self.session.get("http://127.0.0.1:8000/api/v1/channels", timeout=2)"""

target2 = """    def book_channels(self):
        user_name = self.user_name_input.text().strip()"""
replace2 = """    def book_channels(self):
        if getattr(self, 'force_mock', False):
            channels = self.get_selected_channels()
            user_name = self.user_name_input.text().strip()
            for ch in channels:
                if ch in self.channel_nodes:
                    self.channel_nodes[ch].set_booked_by(user_name, True)
            return
            
        user_name = self.user_name_input.text().strip()"""

target3 = """    def release_channels(self):
        user_name = self.user_name_input.text().strip()"""
replace3 = """    def release_channels(self):
        if getattr(self, 'force_mock', False):
            channels = self.get_selected_channels()
            for ch in channels:
                if ch in self.channel_nodes:
                    self.channel_nodes[ch].set_booked_by(None, False)
            return
            
        user_name = self.user_name_input.text().strip()"""

content = content.replace(target1, replace1)
content = content.replace(target2, replace2)
content = content.replace(target3, replace3)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
