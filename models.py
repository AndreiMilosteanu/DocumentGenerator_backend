from tortoise import fields
from tortoise.models import Model

class DocumentThread(Model):
    """
    Represents a conversation thread for a single document (topic).
    Each document has one assistant thread.
    """
    id = fields.UUIDField(pk=True)
    thread_id = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "document_thread"