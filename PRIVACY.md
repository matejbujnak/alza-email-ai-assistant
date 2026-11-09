# Privacy Policy

Email AI Assistant is a proof of concept created for a job application. It is not a service of Alza.cz a.s. and is not affiliated with it. Contact: matej.alza.bot@gmail.com

## What data is processed

The assistant only processes emails sent to its own mailbox, matej.alza.bot@gmail.com: the sender's address, subject, body and attachments. It does not access any other mailbox or Google account.

## How the data is used

- The subject, body and supported attachments are sent to the Google Gemini API to generate a reply. The sender's address is not sent to Gemini.
- The reply is sent back to the sender in the same email thread.
- The assistant uses the free tier of the Gemini API. Under Google's terms, content sent to unpaid Gemini services may be used by Google to improve its products and may be reviewed by humans. **Do not send personal, confidential or sensitive information.**

## Storage and retention

- Emails and replies stay in the assistant's Gmail mailbox.
- Application logs contain message IDs, sender addresses and processing status. They are kept for troubleshooting and deleted after at most 30 days.
- Gemini requests are made with storage disabled, so Google does not keep them as stored interactions.
- Data is not sold or shared with anyone else.

## Google API Services

The use and transfer of information received from Google APIs adheres to the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the Limited Use requirements.

## Deletion

To have your emails and related logs deleted, send a request to matej.alza.bot@gmail.com.
