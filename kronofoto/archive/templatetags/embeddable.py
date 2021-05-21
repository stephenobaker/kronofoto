from django import template
from django.http import QueryDict


register = template.Library()

def make_querydict(constraint):
    qd = QueryDict(mutable=True)
    if constraint:
        qd['constraint'] = constraint
    return qd

@register.inclusion_tag('archive/embeddable.html', takes_context=False)
def embeddable_link(embedded, obj, constraint_expr):
    qd = make_querydict(constraint_expr)
    return dict(text=str(obj), href=obj.get_embedded_url(params=qd) if embedded else obj.get_absolute_url(params=qd))

@register.simple_tag(takes_context=False)
def embeddable_url(embedded, obj, constraint_expr):
    qd = make_querydict(constraint_expr)
    return obj.get_embedded_url(params=qd) if embedded else obj.get_absolute_url(params=qd)

@register.simple_tag(takes_context=False)
def embeddable_json_url(embedded, obj, constraint_expr):
    qd = make_querydict(constraint_expr)
    return obj.get_embedded_json_url(params=qd) if embedded else obj.get_json_url(params=qd)
