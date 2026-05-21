# Instantly.ai Setup Guide for GTM Factory

## Prerequisites

Before the email outreach features work, you need to configure Instantly.ai properly.

## 1. Connect a Sending Email Account

Instantly doesn't send emails itself — it sends through YOUR email account.

### Option A: Personal Gmail (Testing Only)
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification**
3. Search for **App Passwords** → Create one named "Instantly"
4. In Instantly: **Email Accounts** → **Add New** → **Google** → **App Password**
5. Enter your Gmail + the 16-character app password

### Option B: Google Workspace (Production)
1. Purchase a secondary domain (e.g., `getcompany.com`)
2. Set up Google Workspace ($7/mo)
3. Configure DNS records (SPF, DKIM, DMARC)
4. Connect via OAuth in Instantly

## 2. Enable Warmup

**Critical**: New accounts must warm up for 2-4 weeks before cold outreach.

1. In Instantly → **Email Accounts** → Click your account
2. Enable **Warmup** toggle
3. Set warmup volume to start at 5-10 per day
4. Wait at least 14 days before launching campaigns

## 3. Domain Authentication (Production Only)

For custom domains, add these DNS records:

| Record | Type | Purpose |
|--------|------|---------|
| SPF | TXT | Authorizes servers to send on your behalf |
| DKIM | TXT | Digital signature for email integrity |
| DMARC | TXT | Tells receivers how to handle failed auth |

Instantly provides the exact values in **Settings → Domain Authentication**.

## 4. How Campaigns Work

The GTM Factory creates campaigns via API in this order:

1. **Create Campaign** → `POST /api/v2/campaigns`
2. **Add Leads** → `POST /api/v2/leads` (one per contact)
3. **Activate Campaign** → `POST /api/v2/campaigns/{id}/activate`
4. Instantly then sends emails on its schedule through your connected account

## 5. API Key Configuration

Your API key is already configured via the `.env` file:
- **Type**: V2 API key
- **Scopes**: `all:all` (full access)
- **Location**: `.env` → `INSTANTLY_API_KEY`

The server auto-seeds this key into the database on startup.

## 6. Sending Limits

| Account Type | Daily Limit | Recommended |
|-------------|-------------|-------------|
| Personal Gmail | 30/day | 10-15/day |
| Google Workspace | 2,000/day | 30-50/day |
| Dedicated Cold Email | Varies | 30-50/day |

## 7. Credits

Your Instantly account has **1,000 credits**. Each email sent costs credits.
Monitor usage in Instantly → **Settings** → **Billing & Usage**.
