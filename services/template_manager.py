import os
import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from templates.structure import DOCUMENT_STRUCTURE
from datetime import datetime

logger = logging.getLogger("template_manager")

class TemplateManager:
    """
    Manages PDF templates for different document topics.
    Provides methods to select appropriate templates and render them with data.
    """
    
    def __init__(self):
        # Base templates directory
        self.base_dir = Path(__file__).parent.parent / "templates"
        self.pdf_templates_dir = self.base_dir / "pdf_templates"
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.base_dir)),
            autoescape=select_autoescape(["html", "xml"])
        )
        
        # Add custom filters
        self.env.filters['safe_str'] = self.safe_str
        self.env.filters['default_if_none'] = self.default_if_none
        
        # Register the now function for template context
        self.env.globals['now'] = datetime.now
    
    @staticmethod
    def safe_str(value):
        """Safely convert any value to string, including datetime objects"""
        if isinstance(value, datetime):
            return value.strftime('%d.%m.%Y')
        elif value is None:
            return ""
        else:
            return str(value)
    
    @staticmethod
    def default_if_none(value, default=""):
        """Return default value if input is None"""
        return default if value is None else value
    
    def get_template_path(self, topic):
        """
        Get the appropriate template path for a given topic.
        Falls back to default template if topic-specific one doesn't exist.
        """
        # Check if a topic-specific template exists
        topic_template_path = self.pdf_templates_dir / topic / "base.html"
        
        if topic_template_path.exists():
            logger.info(f"Using topic-specific template for {topic}")
            return f"pdf_templates/{topic}/base.html"
        else:
            logger.info(f"No topic-specific template found for {topic}, using default")
            return "doc.html"  # Fallback to default template
    
    def get_structure_for_topic(self, topic):
        """
        Get the document structure for a specific topic.
        """
        if topic in DOCUMENT_STRUCTURE:
            return DOCUMENT_STRUCTURE[topic]
        else:
            logger.warning(f"No structure found for topic: {topic}")
            return []
    
    def prepare_template_data(self, topic, document_data, section_data=None):
        """
        Prepare the data needed for template rendering.
        """
        # Get document structure
        structure = self.get_structure_for_topic(topic)
        
        # Basic template data
        template_data = {
            'title': topic,
            'project_name': document_data.get('project_name', ''),
            'client_name': document_data.get('client_name', ''),
            'project_number': document_data.get('project_number', ''),
            'date': document_data.get('date', datetime.now()),
            'author': document_data.get('author', ''),
            'structure': structure,
            'section_data': section_data or {}
        }
        
        return template_data
    
    def render_template(self, topic, document_data, section_data=None):
        """
        Render the appropriate template for a given topic with provided data.
        """
        try:
            # Get the template path
            template_path = self.get_template_path(topic)
            
            # Load the template
            template = self.env.get_template(template_path)
            
            # Prepare the data
            template_data = self.prepare_template_data(topic, document_data, section_data)
            
            # Render the template
            rendered_html = template.render(**template_data)
            
            return rendered_html
            
        except Exception as e:
            logger.error(f"Error rendering template for topic {topic}: {e}")
            raise 