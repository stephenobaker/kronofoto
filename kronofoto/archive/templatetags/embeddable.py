from django import template

register = template.Library()

@register.inclusion_tag('archive/embeddable.html', takes_context=False)
def embeddable_link(embedded, obj):
    return dict(text=str(obj), href=obj.get_embedded_url() if embedded else obj.get_absolute_url())
