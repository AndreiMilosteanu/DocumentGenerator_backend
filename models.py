from tortoise import fields
from tortoise.models import Model

class Document(Model):
    """
    Represents a document (topic) and stores metadata and generated PDF bytes.
    """
    id = fields.UUIDField(pk=True)
    topic = fields.CharField(max_length=100)
    thread_id = fields.CharField(max_length=255, null=True)
    pdf_data = fields.BinaryField(null=True)  # store generated PDF bytes
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "documents"

class SectionData(Model):
    """
    Stores structured JSON data for each section of a document.
    """
    id = fields.IntField(pk=True)
    document = fields.ForeignKeyField("models.Document", related_name="sections")
    section = fields.CharField(max_length=100)
    data = fields.JSONField()

    class Meta:
        table = "section_data"
        unique_together = (("document_id", "section"),)

class ChatMessage(Model):
    """
    Persists chat history messages and file references for a document.
    """
    id = fields.IntField(pk=True)
    document = fields.ForeignKeyField("models.Document", related_name="messages")
    role = fields.CharField(max_length=10)
    content = fields.TextField(null=True)
    file_path = fields.CharField(max_length=255, null=True)  # optional file upload reference
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chat_messages"