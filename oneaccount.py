#!/usr/bin/env python
from pyquery import PyQuery as pq 
from mechanize import Browser
from datetime import datetime
import os
import glob
import sys
import re

from optparse import OptionParser
from optparse import OptionValueError

from categories import mapping
from categories import guess_category
import settings

LOGIN_URL = "https://service.oneaccount.com/onlineV2/OSV2?event=login&pt=3&brandRef=1"

FILTER = "https://service.oneaccount.com/onlineV2/OSV2?event=showFilter"
def fetch_transactions(startdate=None, enddate=None, visa=False):
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
    br['globalKeyCode'] = settings.CODE
    br['password1'] = settings.PASS[char1-1:char1]
    br['password2'] = settings.PASS[char2-1:char2]
    br['passcode1'] = settings.NUM[num1-1:num1]
    br['passcode2'] = settings.NUM[num2-1:num2]
    br.submit()

    br.open(FILTER)
    br.select_form(nr=0)
    br['periodoption'] = ["byDate"]
    br['startdate'] = startdate.strftime("%d/%m/%Y")
    br['enddate'] = enddate.strftime("%d/%m/%Y")
    if visa:
        br['visa'] = ["True"]
        br['all'] = False
    else:
        br['all'] = ["True"]
    br.submit()
    now = datetime.now()
    return br.response().read()

def parse_transactions(data, visa=False):
    if visa:
        print "!Account"
        print "NVISA"
        print "TCCard"
        print "^"
        print "!Type:CCard"
        print "NVISA"        
    else:
        print "!Account"
        print "NOne account"
        print "TBank"
        print "^"
        print "!Type:Bank"
        print "NOne account"
    
    d = pq(data)
    rows = d('tr.content')
    possible_errors = []
    for row in rows:
        matched_txn = False
        d = pq(row)
        cols = d('td')
        if cols[0].attrib.has_key('colspan'):
            # we reached the end of the table
            break        
        txnid = cols[3].find('input')
        txntype = cols[1].find('span').text
        if txntype in ["VISA PAYMENT",]:
            txnid = ""            
        elif txnid is not None:
            txnid = txnid.attrib['value']
        if txnid is None:
            # may be a 'matched' transaction
            redlink = cols[4].find('a')            
            if redlink is not None and \
                   redlink.attrib['class'] == "redlink":
                matched_txn = True
                idmatch = re.match(r'.*txnSeq=([^"]+).*',
                                   redlink.attrib['href'])
                if idmatch:
                    txnid = idmatch.groups()[0]
        if txnid is None:
            # not yet cleared
            continue
        date = datetime.strptime(cols[0].find('span').text, "%d/%m/%Y")
        txntype = cols[1].find('span').text.strip()
        description = pq("span", cols[2]).html().encode('ascii',
                                                        'ignore')
        if matched_txn:
            matched_category = pq("a.redlink", cols[4])[0].text
            category = re.match(r"Matched \((.*)\)",
                                matched_category).groups()[0]
        else:
            categorybits = pq(cols[4]).html().split("\n")
            if len(categorybits) > 2:
                category = categorybits[2].strip().encode('ascii',
                                                          'ignore')
            else:
                category = ""
        
        debit = cols[5].find('span').text\
                .encode('ascii', 'ignore').replace(",","")
        credit = cols[6].find('span').text\
                 .encode('ascii', 'ignore').replace(",","")
        ref = ""
        who = ""
        if txntype in ["SWITCH POS", "DEBIT POS"]:
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
            category = "Mortgage interest"
        elif txntype in ["SWITCH ATM", "DEBIT ATM"]:
            who = description
        elif txntype == "DIRECT DEBIT":
            who = description
        elif txntype == "VISA PAYMENT":
            who = "VISA"
            ref = description.split("<br/>")[0]
        elif txntype == "VISA":            
            parts = description.split("<br/>")
            whoparts = [x.strip() for x in parts[1].split("   ") if x.strip()]
            ref = parts[0]
            who = whoparts[0]
            if len(whoparts) > 1:
                ref += ": " + " ".join(whoparts[1:])
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
        elif txntype == "VISA CASH":
            parts = description.split("<br/>")
            whoparts = [x.strip() for x in parts[1].split("   ") if x.strip()]
            ref = parts[0]
            who = whoparts[0]
            if len(whoparts) > 1:
                ref += ": " + " ".join(whoparts[1:])
        elif txntype == "DIRECT BANKING":
            parts = description.split("<br/>")
            who = parts[0]
            ref = parts[1]
        else:
            ref = "[UNKNOWN]: " + description
            possible_errors.append(txnid)
        category = guess_category(category,
                                  who,
                                  txntype,
                                  description,
                                  credit=credit,
                                  debit=debit)
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
    if possible_errors:
        sys.stderr.write("!! Had some troubling parsing:\n")
    for e in possible_errors:
        sys.stderr.write("%s\n" % e)

def date_parser(option, opt_str, value, parser):
    if not value:
        return
    try:
        date = datetime.strptime(value, "%Y-%m-%d") 
        setattr(parser.values, option.dest, date)    
    except ValueError:
        raise OptionValueError("Invalid time format: %s" % sys.exc_info()[1])

def parse_options():
    parser = OptionParser()
    parser.set_defaults(accounttype="checking")
    parser.add_option("-v", "--verbose",
                      dest="verbose",
                      action="store_true")
    parser.add_option("-t", "--type",
                      dest="accounttype",
                      help=("Get data for account TYPE "
                            "('visa' or 'checking' [default])"),
                      metavar="TYPE")
    parser.add_option("-f", "--file",
                      dest="filename",
                      help="Read transaction HTML from FILE",
                      metavar="FILE")
    parser.add_option("-s", "--start-date",
                      dest="startdate",
                      action="callback",
                      type="str",
                      callback=date_parser,
                      help="List transactions after STARTDATE (YYYY-mm-dd)")
    parser.add_option("-e", "--end-date",
                      dest="enddate",
                      action="callback",
                      callback=date_parser,
                      type="str",
                      help="List transactions after ENDDATE (YYYY-mm-dd)")
    return parser.parse_args()
    
if __name__ == "__main__":
    options, args = parse_options()
    now = datetime.now()
    startdate = options.startdate
    enddate = options.enddate
    filename = options.filename
    verbose = options.verbose
    if filename and not os.path.exists(filename):
        raise OptionValueError("File %s does not exist" % filename)
    if not enddate:
        enddate = now
    if not startdate:
        files = glob.glob("./one-account-*.html")
        if files:
            files.sort()
            latest = files[-1]
            startdate = datetime.strptime(latest, "./one-account-%Y-%m-%d.html") 
        else:        
            startdate = datetime.strptime(settings.DEFAULT_STARTDATE,
                                          "%Y-%m-%d")
    if verbose:
        print "startdate: %s; enddate: %s" % (startdate, enddate)
    if not filename:
        filename = enddate.strftime("one-account-%Y-%m-%d.html")
    if options.accounttype == "visa":
        filename += ".visa"
    if os.path.exists(filename):
        data = open(filename, "r").read()
    else:
        if options.accounttype == "visa":
            data = fetch_transactions(startdate=startdate,
                                      enddate=enddate,
                                      visa=True)
        else:
            data = fetch_transactions(startdate=startdate,
                                      enddate=enddate)
        f = open(filename, "w")
        f.write(data)
        f.close()
    if options.accounttype == "visa":
        parse_transactions(data, visa=True)
    else:
        parse_transactions(data)
