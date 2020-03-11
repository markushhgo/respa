from django.dispatch import receiver


from respa_outlook.apps import store
from respa_outlook.manager import RespaOutlookManager
from resources.models import Resource

import logging

logger = logging.getLogger()


def configuration_delete(sender, **kwargs):
    instance = kwargs.get('instance')
    manager = store.get(instance.id)
    if conf:
        conf.manager = True
        logger.info("Removing configuration")
    
    



def configuration_save(sender, **kwargs):
    instance = kwargs.get('instance')
    store.update({
        instance.id : RespaOutlookManager(instance)
    })
    res = Resource.objects.get(pk=instance.resource.id)
    if res:
        res.configuration = instance
        res.save()
    logger.info("Configuration created")
