from django.apps import AppConfig
from django.utils.translation import ugettext_lazy


class PluginApp(AppConfig):
    name = 'pretix_itkexport'
    verbose_name = 'ITK export'

    class PretixPluginMeta:
        name = ugettext_lazy('ITK export')
        author = 'Mikkel Ricky'
        description = ugettext_lazy('ITK export')
        visible = True
        version = '1.0.0'

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'pretix_itkexport.PluginApp'
