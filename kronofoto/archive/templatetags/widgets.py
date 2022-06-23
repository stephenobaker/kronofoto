from django import template
from .. import reverse

register = template.Library()

@register.inclusion_tag('archive/grid.html', takes_context=False)
def grid(page_obj):
    return dict(page_obj=page_obj)

@register.inclusion_tag('archive/photo-link.html', takes_context=False)
def h700_link(photo):
    return dict(photo=photo)

@register.inclusion_tag('archive/page-links.html', takes_context=False)
def page_links(formatter, page_obj, target=None):
    links = [{'label': label} for label in ['First', 'Previous', 'Next', 'Last']]
    if page_obj.number != 1:
        links[0]['url'] = formatter.page_url(1)
        links[0]['url_json'] = formatter.page_url(1, json=True)
        links[0]['target'] = target
        links[1]['url'] = formatter.page_url(page_obj.previous_page_number())
        links[1]['url_json'] = formatter.page_url(page_obj.previous_page_number(), json=True)
        links[1]['target'] = target
    if page_obj.has_next():
        links[2]['url'] = formatter.page_url(page_obj.next_page_number())
        links[2]['url_json'] = formatter.page_url(page_obj.next_page_number(), json=True)
        links[2]['target'] = target
    if page_obj.number != page_obj.paginator.num_pages:
        links[3]['url'] = formatter.page_url(page_obj.paginator.num_pages)
        links[3]['url_json'] = formatter.page_url(page_obj.paginator.num_pages, json=True)
        links[3]['target'] = target
    return dict(
        links=links,
        page_obj=page_obj
    )


@register.inclusion_tag('archive/grid-content.html', takes_context=False)
def grid_content(collection_name, formatter, page_obj):
    return dict(
        collection_name=collection_name,
        formatter=formatter,
        page_obj=page_obj,
    )

@register.inclusion_tag('archive/view-buttons.html', takes_context=False)
def view_buttons(timeline_url, timeline_json_url, grid_url, grid_json_url):
    return dict(
        timeline_url=timeline_url,
        timeline_json_url=timeline_json_url,
        grid_url=grid_url,
        grid_json_url=grid_json_url,
    )

@register.inclusion_tag('archive/photo-details.html', takes_context=False)
def photo_details(photo, page, years, timeline, timeline_key, prev_page, next_page):
    return dict(
        photo=photo,
        page=page,
        years=years,
        timeline=timeline,
        timeline_key=timeline_key,
        prev_page=prev_page,
        next_page=next_page,
    )

@register.simple_tag
def absolutify(url):
    return reverse.as_absolute(url)
