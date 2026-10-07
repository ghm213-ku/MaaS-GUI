file_path = "ui/main_window.py"
with open(file_path, "r") as f:
    content = f.read()

target = """        try:
            import requests
            resp = requests.post("http://127.0.0.1:8000/auth/login", json={"username": username, "password": password}, timeout=5)
            if resp.status_code == 401:
                QMessageBox.warning(self, "Authentication Failed", "Invalid credentials")
                return
            resp.raise_for_status()
            self.auth_token = resp.json().get("token")
            self.login_username = username
        except Exception as e:
            QMessageBox.warning(self, "Connection Error", f"Could not connect to backend to authenticate:\\n{e}")
            return"""

replacement = """        if getattr(self, 'force_mock', False):
            self.auth_token = "mock_token"
            self.login_username = username
        else:
            try:
                import requests
                resp = requests.post("http://127.0.0.1:8000/auth/login", json={"username": username, "password": password}, timeout=5)
                if resp.status_code == 401:
                    QMessageBox.warning(self, "Authentication Failed", "Invalid credentials")
                    return
                resp.raise_for_status()
                self.auth_token = resp.json().get("token")
                self.login_username = username
            except Exception as e:
                QMessageBox.warning(self, "Connection Error", f"Could not connect to backend to authenticate:\\n{e}")
                return"""

content = content.replace(target, replacement)

with open(file_path, "w") as f:
    f.write(content)
