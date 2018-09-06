# -*- coding: utf-8 -*-
from __future__ import print_function
import time
import os
import json
import datetime
import smtplib
import logging
from pprint import pprint
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import ynab
from ynab.rest import ApiException
from jinja2 import Environment


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

TEXT = """
{{ title }}

{% for tx in txs %}
{{ tx[0] }}: {{ tx[1] }}
{% endfor %}
"""

HTML = """
<b><i>{{ title }}</i></b>
<br>
<table class="gridtable" style="font-family: verdana,arial,sans-serif;font-size: 11px;color: #333333;border-width: 1px;border-color: #666666;border-collapse: collapse;">
<tr>
    <th style="border-width: 1px;padding: 8px;border-style: solid;border-color: #666666;background-color: #dedede;">Kategorija</th><th style="border-width: 1px;padding: 8px;border-style: solid;border-color: #666666;background-color: #dedede;">Ukupan iznos</th>
</tr>
{% for tx in txs %}
<tr>
    <td style="border-width: 1px;padding: 8px;border-style: solid;border-color: #666666;background-color: #ffffff;">{{ tx[0] }}</td><td style="border-width: 1px;padding: 8px;border-style: solid;border-color: #666666;background-color: #ffffff;">{{ tx[1] }}</td>
</tr>
{% endfor %}
</table>
"""

if __name__ == '__main__':
    # Get configuration from environment
    api_key = os.environ.get('YNAB_API_KEY')
    budget_name = os.environ.get('YNAB_BUDGET_NAME')
    mail_user = os.environ.get('YNAB_MAIL_USER')
    mail_password = os.environ.get('YNAB_MAIL_PASSWORD')
    # Comma separated list of mails to send the report to
    mails_send = os.environ.get('YNAB_MAILS_SEND')

    # Initialize the API
    log.info('Initializing API...')
    ynab_config = ynab.configuration.Configuration()
    ynab_config.api_key['Authorization'] = api_key
    ynab_config.api_key_prefix['Authorization'] = 'Bearer'
    api_client = ynab.api_client.ApiClient(configuration=ynab_config)
    api_budget = ynab.BudgetsApi(api_client)
    api_tx = ynab.TransactionsApi(api_client)
    api_cat = ynab.CategoriesApi(api_client)

    # Get budget ID
    budget_id = None
    for budget in api_budget.get_budgets().data.budgets:
        if budget.name == budget_name:
            budget_id = budget.id
            break
    else:
        raise Exception('Budget with name "%s" not found' % budget_name)

    # Set times
    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)
    since_date = week_ago.strftime('%Y-%m-%d')

    # Get transactions
    log.info('Fetching all transactions since %s...' % since_date)
    api_response = api_tx.get_transactions(budget_id, since_date=since_date)
    txs = api_response.to_dict()['data']['transactions']

    # Calculate spending
    res = {}
    for tx in txs:
        if tx['subtransactions']:
            tx = tx['subtransactions']
        else:
            tx = [tx]
        for t in tx:
            if t['amount'] > 0:
                continue
            tid = t['category_id']
            if tid not in res:
                res[tid] = {
                    'amount': 0.0,
                }
            res[tid]['name'] = t.get('category_name', None)
            res[tid]['amount'] += t['amount']

    # Get category names
    for tid, t in res.iteritems():
        if t['name'] is not None:
            continue
        cat = api_cat.get_category_by_id(budget_id, tid).to_dict()['data']['category']
        res[tid]['name'] = cat['name']

    # Sort top 10 results
    out = []
    for r in (sorted(res.values(), key=lambda k: k['amount'])):
        amount = u'%4.2f €' % abs(r['amount'] / 1000)
        out.append((u'%s' % r['name'], amount, ))
        if len(out) >= 10:
            break

    # Prepare results
    log.info('Preparing mail...')
    mail_title = 'YNAB report for week of %s (from %s)' % (today.strftime('%Y-%W') ,week_ago.strftime('%a %Y-%m-%d'))
    mail_html = Environment().from_string(HTML).render(
        title=mail_title,
        txs=out,
        )
    mail_text = Environment().from_string(TEXT).render(
        title=mail_title,
        txs=out,
        )

    # Prepare mails
    msg = MIMEMultipart('alternative')
    msg['Subject'] = mail_title
    msg['From'] = mail_user
    part1 = MIMEText(mail_text.encode('utf-8'), 'plain', 'utf-8')
    part2 = MIMEText(mail_html.encode('utf-8'), 'html', 'utf-8')
    msg.attach(part1)
    msg.attach(part2)

    # Send mails
    for mail_to in mails_send.split(','):
        try:
            msg['To'] = mail_to
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            server.ehlo()
            server.login(mail_user, mail_password)
            server.sendmail(mail_user, mail_to, msg.as_string())
            server.close()
            log.info('Sent mail to %s' % mail_to)
        except Exception as e:
            log.error('Error sending mail to %s: %s' % (mail_to, e))
