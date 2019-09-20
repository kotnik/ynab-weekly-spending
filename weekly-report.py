# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import time
import os
import json
import datetime
import smtplib
from pprint import pprint as pp

import hammock
import requests
from logzero import logger as log
from jinja2 import Environment


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

    ynab = hammock.Hammock(
        "https://api.youneedabudget.com/v1",
        headers={"Authorization": "Bearer %s" % api_key},
    )

    budgets = ynab.budgets.GET().json()['data']['budgets']
    for budget in budgets:
        if budget['name'] == budget_name:
            budget_id = budget['id']
            budget_full = ynab.budgets(budget_id).GET().json()['data']['budget']
            category_groups = budget_full['category_groups']
            break
    else:
        raise Exception('Budget with name "%s" not found' % budget_name)

    log.info('Using %s (%s)', budget_name, budget_id)

    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)
    since_date = week_ago.strftime('%Y-%m-%d')

    log.info('Fetching all transactions since %s...', since_date)

    transactions = ynab.budgets(budget_id).transactions.GET('?since_date=%s' % since_date).json()['data']['transactions']

    # Calculate spending
    res = {}
    for tx in transactions:
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
        cat = ynab.budgets(budget_id).categories(tid).GET().json()['data']['category']
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
