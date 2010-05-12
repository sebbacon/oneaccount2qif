from pyquery import PyQuery as pq 
from mechanize import Browser
from datetime import datetime
import os

from settings import *

LOGIN_URL = "https://service.oneaccount.com/onlineV2/OSV2?event=login&pt=3&brandRef=1"

FILTER = "https://service.oneaccount.com/onlineV2/OSV2?event=showFilter"
def fetch_transactions(startdate=None, enddate=None):
    br = Browser()
    br.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]
    br.set_handle_equiv(True)
    br.set_handle_gzip(True)
    br.set_handle_redirect(True)
    br.set_handle_referer(True)
    br.set_handle_robots(False)
    br.open(LOGIN_URL)

    d = pq(br.response().read())
    labels = d('td strong')
    char1 = int(labels[2].text.strip())
    char2 = int(labels[3].text.strip())
    num1 = int(labels[5].text.strip())
    num2 = int(labels[6].text.strip())
    br.select_form(nr=0)
    br['globalKeyCode'] = CODE
    br['password1'] = PASS[char1-1:char1]
    br['password2'] = PASS[char2-1:char2]
    br['passcode1'] = NUM[num1-1:num1]
    br['passcode2'] = NUM[num2-1:num2]
    br.submit()

    br.open(FILTER)
    br.select_form(nr=0)
    if startdate and enddate:
        br['all'] = ["True"]
        br['periodoption'] = ["byDate"]
        br['startdate'] = startdate
        br['enddate'] = enddate
    br.submit()
    now = datetime.now()
    f = open(now.strftime("one-account-%Y-%m-%d.html"), "w")
    f.write(br.response().read())
    f.close()

def parse_transactions(data):
    print "!Account"
    print "NOne account"
    print "TBank"
    print "^"
    print "!Type:Bank"
    print "NOne account"
    
    d = pq(data)
    rows = d('tr.content') # or something
    for row in rows:
        d = pq(row)
        cols = d('td')
        if cols[0].attrib.has_key('colspan'):
            # we reached the end of the table
            break        
        txnid = cols[3].find('input')
        txntype = cols[1].find('span').text
        if txntype == "VISA PAYMENT":
            txnid = ""            
        elif txnid is None:
            # not yet cleared
            continue
        else:
            txnid = txnid.attrib['value']
        date = datetime.strptime(cols[0].find('span').text, "%d/%m/%Y")
        txntype = cols[1].find('span').text.strip()
        description = pq("span", cols[2]).html().encode('ascii', 'ignore')
        categorybits = pq(cols[4]).html().split("\n")
        if len(categorybits) > 2:
            category = categorybits[2].strip().encode('ascii',
                                                      'ignore')
        else:
            category = ""        
        debit = cols[5].find('span').text.encode('ascii', 'ignore').replace(",","")
        credit = cols[6].find('span').text.encode('ascii', 'ignore').replace(",","")
        ref = ""
        who = ""
        if txntype == "SWITCH POS":
            ref, who = description.split("<br/>")
        elif txntype == "BACS CREDIT" or txntype == "CHAPS":
            parts = description.split("<br/>")
            if len(parts) == 2:
                who = parts[0]
                ref = parts[1]
            else:
                who = parts[0]
        elif txntype == "STAND ORDER":
            parts = description.split("<br/>")
            if len(parts) == 2:
                who = parts[0]
                ref = parts[1]
            else:
                who = parts[0]
        elif txntype == "INTEREST":
            who = "ONE ACCOUNT"
            ref = description
        elif txntype == "SWITCH ATM":
            who = description
        elif txntype == "DIRECT DEBIT":
            who = description
        elif txntype == "VISA PAYMENT":
            who = "VISA"
            ref = description.split("<br/>")[0]
        elif txntype == "CHEQUE":
            who = ""
            ref = description
        elif txntype == "PAYMENT":
            parts = description.split("<br/>")
            who = parts[0]
            ref = parts[1]
        elif not txntype and credit:
            txntype = "CHEQUE"
            who = ""
            ref = description
        elif txntype == "TELLER CREDIT" and credit:
            who = ""
            ref = description
        elif not txntype and description== "FOREIGN CHARGE":
            txntype = description
            who = ""
            ref = description
        else:
            import sys
            print txntype, "!!!!!!!!!!!!!!!", who, txnid
            sys.exit(1)
        ref = ref.encode('ascii', 'ignore')
        print date.strftime("D%m/%d/%Y")
        if credit:
            print "T%s" % credit
        elif debit:
            print "T-%s" % debit
        print "M%s: %s" % (txntype, ref)
        print "N%s" % txnid
        print "P%s" % who
        print "L%s" % category
        print "^"

now = datetime.now()
enddate = now.strftime("%d/%m/%Y")
filename = now.strftime("one-account-%Y-%m-%d.html")
if os.path.exists(filename):
    data = open(filename, "r").read()
    parse_transactions(data)
else:
    fetch_transactions(startdate=STARTDATE, enddate=enddate)
