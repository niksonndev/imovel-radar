# ── DynamoDB — estado de conversa do bot (ADR 0006) ──────────────────────────
# Persistência PTB (user_data/chat_data/conversation_data/bot_data) keyed por
# chat_id + store. TTL nativo descarta drafts abandonados; `version` (gravado
# pelo código) dá o optimistic concurrency do put condicional.
# Billing on-demand: free tier permanente (25 GB / 25 RCU / 25 WCU).

resource "aws_dynamodb_table" "conversation_state" {
  name         = "${var.project}-${var.environment}-conversation-state"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "chat_id"
  range_key = "store"

  attribute {
    name = "chat_id"
    type = "N"
  }

  attribute {
    name = "store"
    type = "S"
  }

  ttl {
    enabled        = true
    attribute_name = "ttl"
  }
}