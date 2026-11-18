# Sample Knowledge Base

Place the documents you want the support agent to use in this folder.

Supported formats:

- `.txt`
- `.md`
- text-based `.pdf`

For the current MVP, upload these files through the frontend using **Upload document**. The backend will extract the text, split it into chunks, generate Gemini embeddings, and store the indexed content locally.

Suggested documents:

- `product-faq.md`
- `refund-policy.md`
- `account-help.md`
- `shipping-policy.md`
