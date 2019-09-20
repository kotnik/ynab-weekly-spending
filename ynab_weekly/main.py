# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import time
import os
import json
import datetime
import smtplib
import argparse
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


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ynab-api-key", help="YNAB API key", type=str, required=True)
    parser.add_argument("--ynab-budget-name", help="YNAB API key", type=str, required=True)
    parser.add_argument("--mailgun-api-key", help="Mailgun API key", type=str, required=True)
    parser.add_argument("--mailgun-api-domain", help="Mailgun API domain", default="api.eu.mailgun.net", type=str)
    parser.add_argument("--mailgun-domain", help="Mailgun domain", type=str, required=True)
    parser.add_argument("--mails", nargs="+", help="Mails to send report to", required=True)
    options = parser.parse_args(sys.argv[1:])

    ynab = hammock.Hammock(
        "https://api.youneedabudget.com/v1",
        headers={"Authorization": "Bearer %s" % options.ynab_api_key},
    )

    budgets = ynab.budgets.GET().json()['data']['budgets']
    for budget in budgets:
        if budget['name'] == options.ynab_budget_name:
            budget_id = budget['id']
            budget_full = ynab.budgets(budget_id).GET().json()['data']['budget']
            category_groups = budget_full['category_groups']
            break
    else:
        raise Exception('Budget with name "%s" not found' % options.ynab_budget_name)

    log.info('Using %s (%s)', options.ynab_budget_name, budget_id)

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

    for mail_to in options.mails:
        log.info('Sending mail "%s" to %s...', mail_title, mail_to)
        result = requests.post(
            "https://%s/v3/%s/messages" % (options.mailgun_api_domain, options.mailgun_domain),
            auth=("api", options.mailgun_api_key),
            data={"from": "YNAB Reporter <yanb@%s>" % options.mailgun_domain,
                  "to": mail_to,
                  "subject": mail_title,
                  "text": mail_text.encode('utf-8'),
                  "html": mail_html.encode('utf-8')
        })
        log.info('Mailgun response: %s', result.status_code)
