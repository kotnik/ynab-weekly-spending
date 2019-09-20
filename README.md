# YNAB Weekly Spending Reports with Python

If you want weekly mail with top 10 spending categories in [You Need a Budget](https://ynab.com/referral/?ref=2QOWY7f12Aeo5ASi&utm_source=customer_referral), you are in the right place.

This application is inspired by [YNAB Weekly Spending Reports with Google Apps Script](https://www.connorcg.com/ynab-spending-report-google-apps-script.html) by [Connor Griffin](https://gist.github.com/ConnorGriffin), only in Python instead of JavaScript.

## How to Run

Easy. You need:

* [YNAB Personal Access Token](https://api.youneedabudget.com/#authentication-overview).
* Your [Mailgun](https://mailgun.com) personal [token](https://app.mailgun.com/app/account/security/api_keys) (it's free to send up to 10k mails).
* A place to run Python, any hosting option will do or you can use your computer!

Now, after making sure you have all of the above, install this package:

```
pip2 install --user YNAB-Weekly
```

That is all, we are ready! Use this to run:

```
ynab-weekly \
    --ynab-api-key     YNAB_KEY       \
    --ynab-budget-name "Budged name"  \
    --mailgun-api-key  MAILGUN_KEY    \
    --mailgun-domain   MAILGUN_DOMAIN \
    --mails            me@myhouse.com my-so@myhouse.com
```

Please report bugs in issues.

## How to run in development mode

```
virtualenv -p python2 .env
source .env/bin/activate
pip install --editable .
```
