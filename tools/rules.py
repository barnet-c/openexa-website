"""The site's content rules (from the user and the CEO; see CLAUDE.md), shared by check_static.py and verify_v9.py."""
import re

# no exchange, broker or clearing-house names; no office address, phone or personal email; no pitch-deck ARR figures
FORBIDDEN = re.compile(r"NASDAQ|NYSE|TradeStation|Interactive Brokers|DTCC|704 458|Campus Pkwy|ajit@|\$100M\+ ARR|\$1B\+ ARR", re.I)
# the team is public on company.html; blog bylines (blog/) are the only other place names may appear.
PEOPLE = re.compile(r"Ajit|Dubey|Leung|Lockhart|Gamolsky|Choudhri|Schuster|Parekh|Sinha|Ekeroma|Nanawati|Mehta|Kannan|Philip Bond", re.I)
TEAM_NAMES = ["Ajit K Dubey", "Dr. Tim Leung", "Mike Lockhart", "Victor Gamolsky", "Shalabh Choudhri", "John Schuster", "Subuddh Parekh",
              "Abhishek Sinha", "Dr. Julius E. Ekeroma", "Dipit Nanawati", "Kumar Mehta", "Sreeram Kannan", "Dr. Philip Bond"]
# Barnet Sherman left the team (now a customer) and must not appear anywhere.
GONE = re.compile(r"Barnet|Sherman|Braintree|TIAA", re.I)
