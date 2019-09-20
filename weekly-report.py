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
import requests
from ynab.rest import ApiException
from jinja2 import Environment


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)


TEXT = """
{% for tx in txs %}
{{ tx[0] }}: {{ tx[1] }}
{% endfor %}
"""


HTML = """
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


def _get_group_name_by_id(groups, group_id):
    for group in groups:
        if group_id == group['id']:
            return group['name']
    return ''


def send_mail(to, subject, text, html):
    mailgun_key = os.environ.get('MAILGUN_API_KEY')
    mailgun_api_domain = os.environ.get('MAILGUN_API_DOMAIN', 'api.mailgun.net')
    mailgun_domain = os.environ.get('MAILGUN_DOMAIN')

    return requests.post(
        "https://%s/v3/%s/messages" % (mailgun_api_domain, mailgun_domain),
        auth=("api", mailgun_key),
        data={"from": "YNAB Reporter <yanb@%s>" % mailgun_domain,
              "to": to,
              "subject": subject,
              "text": text,
              "html": html})


if __name__ == '__main__':
    # Get configuration from environment
    api_key = os.environ.get('YNAB_API_KEY')
    budget_name = os.environ.get('YNAB_BUDGET_NAME')
    # Comma separated list of mails to send the report to
    mails_send = os.environ.get('YNAB_SEND_TO', None)

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
            budget = api_budget.get_budget_by_id(budget_id).to_dict()['data']['budget']
            category_groups = budget['category_groups']
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
        if tid is None:
            res[tid]['name'] = 'Transfer'
            continue
        cat = api_cat.get_category_by_id(budget_id, tid).to_dict()['data']['category']
        parent_cat = _get_group_name_by_id(category_groups, cat['category_group_id'])
        res[tid]['name'] = parent_cat + ': ' + cat['name']

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

    if mails_send is None:
        print(mail_text)
    else:
        for mail_to in mails_send.split(','):
            log.info('Sending mail "%s" to %s...', mail_title, mail_to)
            result = send_mail(mail_to, mail_title, mail_text.encode('utf-8'), mail_html.encode('utf-8'))
            log.info(result)
