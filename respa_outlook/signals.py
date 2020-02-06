from django.dispatch import receiver


from respa_outlook.apps import store
from respa_outlook.models import RespaOutlookConfiguration


def configuration_delete(sender, **kwargs):
    instance = kwargs.get('instance')
    print('Configuration %s deleted' % sender.name)
    store.pop(instance.id)




def configuration_save(sender, **kwargs):
    instance = kwargs.get('instance')
    print('New configuration added to: %s' % instance.name)
    store.update({
        instance.id : instance
    })
