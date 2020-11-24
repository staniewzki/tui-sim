#!/bin/python3

import cmd, os, requests, getpass, pickle, json
from bs4 import BeautifulSoup
from texttable import Texttable

url = "https://sim.13lo.pl"
config_path = os.path.expanduser("~/.tui-sim/")

def get_login(session):
    soup = BeautifulSoup(session.get(url).text, "html.parser")
    login = soup.find("a", {"class": "user dropmenu-toggle"})
    if login == None: 
        return False
    else:
        return login.findAll(text=True)[0]

def log_in(session):
    login = input("login: ")
    password = getpass.getpass("password: ")
    data = {"username": login, "password": password, "persistent-login": "on", "csrf_token": ""}
    session.post(url + "/login", data=data)

    if not os.path.exists(config_path):
        os.mkdir(config_path)
    with open(config_path + "session", "wb") as f:
        pickle.dump(session.cookies, f)
    return session

def query(session, path):
    token = session.cookies.get_dict()["csrf_token"]
    return session.post(url + "/api/" + path, data={"csrf_token": token})

def get_user_id(session):
    soup = BeautifulSoup(session.get(url).text, "html.parser")
    dropdown = soup.find("ul")
    for a in dropdown:
        return a["href"]

def red(string):
    return "\033[31m" + string + "\033[0m"
def green(string):
    return "\033[32m" + string + "\033[0m"
def yellow(string):
    return "\033[33m" + string + "\033[0m"
def purple(string):
    return "\033[35m" + string + "\033[0m"
def cyan(string):
    return "\033[36m" + string + "\033[0m"
def bold(string):
    return "\033[1m"  + string + "\033[0m"

def color(string, desc):
    if desc == "red":
        return red(string)
    elif desc == "green":
        return green(string)
    elif desc == "yellow":
        return yellow(string)
    elif desc == "purple":
        return purple(string)
    else:
        return string

def print_table(html):
    soup = BeautifulSoup(html, "html.parser")
    table = Texttable()
    row = [""] * 5

    table.set_cols_valign(["m"] * 5)
    for t in soup.children:
        for s in t.children:
            for line in s.children:
                l = line.findAll(text=True)
                if len(l) == 4:
                    l.append("")
                else:
                    if row[0] != "":
                        table.add_row(row)
                        row = [""] * 5

                for i in range(5):
                    if row[i] == "":
                        row[i] = l[i]
                    elif l[i] != "":
                        row[i] += "\n" + l[i]

        break

    if row[0] != "":
        table.add_row(row)

    print(table.draw())

class SimShell(cmd.Cmd):
    prompt = "sim >>> "
    session = requests.Session()
    directory = "~"
    username = None
    contest_id = None

    def update_prompt(self):
        self.prompt = bold(cyan(self.username + "@sim ")) + self.directory + " >>> "

    def start_session(self):
        try:
            with open(config_path + "session", "rb") as f:
                self.session.cookies.update(pickle.load(f))
        except:
            self.session = requests.Session()

        if get_login(self.session) == False: 
            while True:
                self.session = log_in(self.session)
                if get_login(self.session) == False:
                    print("Error: Invalid login or password")
                else:
                    break

        self.username = get_login(self.session)
        self.update_prompt()

    def do_logout(self, line):
        """logs the user out"""
        os.remove(config_path + "session")
        self.start_session()

    def do_ls(self, line):
        """list contests, or lists round and problems if you are in a contest"""
        if self.contest_id == None:
            json_data = query(self.session, "contests").json()
            for line in json_data:
                if type(line) is list:
                    print("[" + str(line[0]) + "] " + line[1]) 
        else:
            try:
                json_data = query(self.session, "contest/c" + self.contest_id).json()
            except:
                print("Error: Selected contest is invalid")
                return

            round_dict = {}
            for line in json_data[2]:
                round_dict[line[0]] = []
            for line in json_data[3]:
                round_dict[line[1]].append(line)
            for line in json_data[2]:
                print(bold(str(line[1]) + ":"))
                for problem in round_dict[line[0]]:
                    output = "  [" + str(problem[0]) + "] " + problem[5]
                    output = color(output, problem[9])
                    print(output)

    def do_cd(self, line):
        """enter a contest by id"""
        if line == "..":
            self.contest_id = None
            self.directory = "~"
        else:
            q = query(self.session, "contest/c" + line)
            try:
                json_data = q.json()
            except:
                print("Error: Invalid contest id")
                return
            self.contest_id = line
            for line in json_data:
                if type(line) is list:
                    if not (type(line[0]) is list):
                        self.directory = line[1]
        
        self.update_prompt()

    def do_submissions(self, line):
        """show submissions in a contest"""
        if self.contest_id == None:
            print("Error: Enter a contest first")
        else:
            uid = get_user_id(self.session)[3::]
            if line == "":
                q = query(self.session, "submissions/C" + self.contest_id + "/u" + uid)
                try:
                    json_data = q.json()
                except:
                    print("Error: Selected contest is invalid")
                    return

                json_data.reverse()
                for line in json_data:
                    if type(line) is list:
                        output = "[" + str(line[0]) + "] " + line[15] + " | " + line[10] + " | " + str(line[17])
                        output = color(output, line[16][0])
                        print(output)

    def do_submit(self, line):
        """submit [problem_id] [file]"""
        line = line.split(" ")
        if len(line) < 2:
            print("Error: This command requires two arguments")
        else:
            q = query(self.session, "contest/p" + line[0])
            try:
                json_data = q.json()
            except:
                print("Error: Invalid problem id")
                return

            submit_url = url + "/api/submission/add/p" + str(json_data[3][0][2]) + "/cp" + line[0]
            try:
                f = open(line[1], "rb")
            except:
                print("Error: File does not exist")
                return
            token = self.session.cookies.get_dict()["csrf_token"]
            data = {"language": "cpp17", "code": "", "csrf_token": token}

            resp = self.session.post(submit_url, files={"solution": f}, data=data)
            print("Submit id: " + resp.text)

    def do_details(self, line):
        """prints details of a submission"""
        q = query(self.session, "submissions/=" + line)
        try:
            json_data = q.json()
        except:
            print("Error: Invalid submission id")
            return
        
        try:
            col, status = json_data[1][16]
        except:
            print("Error: Invalid submission id")
            return

        if status == "Compilation failed":
            print(json_data[1][8] + " | " + color(status, col))
            soup = BeautifulSoup(json_data[1][19], "html.parser")
            for line in soup.findAll(text=True):
                print(line)
        else:
            print(json_data[1][8] + " | " + color(status, col) + " | " + str(json_data[1][17]))
            print(bold("Initial tests:"))
            print_table(json_data[1][19]) 
            print(bold("Final tests:"))
            print_table(json_data[1][20]) 

    def do_statement(self, line):
        """open statement"""
        q = query(self.session, "contest/p" + line)
        try:
            json_data = q.json()
        except:
            print("Error: Invalid problem id")
            return

        problem_name = json_data[3][0][5]
        resp = query(self.session, "download/statement/contest/p" + line + "/" + problem_name)

        statement_path = "/tmp/" + problem_name + ".pdf"
        with open(statement_path, "wb") as f:
            f.write(resp.content)

        def open_statement():
            os.system("xdg-open '" + statement_path + "' > /dev/null 2>&1")

        import threading
        t = threading.Thread(target=open_statement)
        t.daemon = True
        t.start()

    def do_exit(self, line):
        """exit the shell"""
        return True

    def do_EOF(self, line):
        """exit the shell"""
        return True

if __name__ == '__main__':
    shell = SimShell()
    shell.start_session()
    shell.cmdloop()
