# ☁️ How to Enable Claude AI in AWS Bedrock

You are seeing an error because AWS requires you to explicitly request access to Anthropic's Claude models before you can use them.

**Error Message:**
> `Model use case details have not been submitted for this account.`

## ✅ Step-by-Step Fix

### 1. Log in to AWS Console
Go to [https://console.aws.amazon.com/bedrock/](https://console.aws.amazon.com/bedrock/) and ensure you are in the **us-east-1** (N. Virginia) region.

### 2. Go to Model Access
In the left sidebar, scroll down to the bottom and click **Model access**.

### 3. Edit Access
Click the orange **Manage model access** button (usually top right).

### 4. Select Claude
1. Scroll down to the **Anthropic** section.
2. Check the box next to **Claude 3 Haiku**.
   - *Note: You might need to submit a "Use Case Details" form first. If so, click the button to submit it. It's a short form asking what you're building.*
   - *For "Use Case", you can write: "Analyzing open source repository documentation for quality scoring."*

### 5. Save Changes
Click **Save changes** at the bottom.

### 6. Wait for "Access Granted"
It usually takes **1-5 minutes** for the status to change to "Access granted" (green).

---

## 🔄 Verification

Once the status says "Access granted", run the verification script again:

```bash
export ENABLE_LLM=true
python verify_bedrock.py
```

You should see:
> `🎉 REAL BEDROCK API CALL SUCCEEDED!`

---

## ⚠️ If You Cannot Do This Right Now

**Don't worry!** The system is designed to handle this.

- The code automatically detects the "Access Denied" error.
- It automatically falls back to **Stub Mode**.
- Your scoring pipeline **will still work** (it just won't use the AI for summaries).

You can continue using the tool as-is.
