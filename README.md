# YNAB Weekly Spending Reports with Python

If you want weekly mail with top 10 spending categories in [You Need a Budget](https://ynab.com/referral/?ref=2QOWY7f12Aeo5ASi&utm_source=customer_referral), you are in the right place.

This application is inspired by [YNAB Weekly Spending Reports with Google Apps Script](https://www.connorcg.com/ynab-spending-report-google-apps-script.html) by [Connor Griffin](https://gist.github.com/ConnorGriffin), only in Python instead of JavaScript.

## How to Run

Easy. You need:

* [YNAB Personal Access Token](https://api.youneedabudget.com/#authentication-overview),
* Google mail with app password created, and
* a place to run Python, any hosting option will do or you can use your computer!

Now, after cloning this code, run this inside of it:

```
virtualenv -p python2 .env
source .env/bin/activate
pip install -r requirements.txt
```

After this, you will need to set up environment variables with your configuration. Or, update following snippet, and use it to run:

```
YNAB_API_KEY='Your YNAB personal access token'             \
YNAB_BUDGET_NAME='Name of your budget'                     \
YNAB_MAIL_USER='Your Google mail'                          \
YNAB_MAIL_PASSWORD='Your Google password, or app password' \
YNAB_MAILS_SEND='me@myhouse.com,my-so@myhouse.com'         \
./.env/bin/python weekly-report.py
```

Please report bugs in issues here.
