from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import TagRelationship


@receiver(post_save, sender=TagRelationship)
def sync_symmetric_inverse(sender, instance: TagRelationship, created, raw, **kwargs):
    """
    Keeps the inverse row of a symmetric TagRelationship in sync so callers
    only ever need to create one direction.

    Uses .update() on the queryset (not .save()) when adjusting an existing
    inverse row, specifically to avoid re-triggering this signal and causing
    infinite recursion.
    """
    if raw:
        # Fixture loading — don't try to derive/sync anything.
        return

    if not instance.is_symmetric:
        return

    inverse, inverse_created = TagRelationship.objects.get_or_create(
        from_tag=instance.to_tag,
        to_tag=instance.from_tag,
        relationship_type=instance.relationship_type,
        defaults={
            "strength": instance.strength,
            "is_symmetric": True,
            "is_system_generated": True,
        },
    )

    if not inverse_created and (
        inverse.strength != instance.strength or not inverse.is_symmetric
    ):
        TagRelationship.objects.filter(pk=inverse.pk).update(
            strength=instance.strength,
            is_symmetric=True,
        )