from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.utils.safestring import mark_safe
from .models import Photo, Tag, Term, PhotoTag, Donor, NewCutoff
from django.db.models import Count
from django.conf import settings
from django.urls import reverse

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ['tag']


@admin.register(NewCutoff)
class NewCutoffAdmin(admin.ModelAdmin):
    pass


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    search_fields = ['last_name', 'first_name']

    list_display = ('__str__', 'donated', 'scanned')

    def scanned(self, obj):
        return '{} photos'.format(obj.scanned_count)

    def donated(self, obj):
        return '{} photos'.format(obj.donated_count)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate_scannedcount().annotate_donatedcount()

    scanned.admin_order_field = 'scanned_count'
    donated.admin_order_field = 'donated_count'


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    pass


class TagInline(admin.TabularInline):
    model = PhotoTag
    extra = 1
    fields = ['tag', 'accepted', 'submitter']
    readonly_fields = ['submitter']

    def submitter(self, instance):
        creators = ', '.join(
            '<a href="{url}">{username}</a>'.format(
                url=reverse('admin:auth_user_change', args=[user.id]),
                username=user.username,
            )
            for user in instance.creator.all()
        )
        return mark_safe(creators)


class TagFilter(admin.SimpleListFilter):
    title = "tag status"
    parameter_name = "phototag__accepted"

    def lookups(self, request, model_admin):
        return (
            ("needs approval", "needs approval"),
            ("approved", "approved"),
        )

    def queryset(self, request, queryset):
        if self.value() == 'approved':
            return queryset.filter(phototag__accepted=True)
        elif self.value() == "needs approval":
            return queryset.filter(phototag__accepted=False)


class YearIsSetFilter(admin.SimpleListFilter):
    title = "photo dated"
    parameter_name = "dated"

    def lookups(self, request, model_admin):
        return (
            ("Yes", "Yes"),
            ("No", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == 'Yes':
            return queryset.filter(year__isnull=False)
        elif self.value() == 'No':
            return queryset.filter(year__isnull=True)


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    readonly_fields = ["h700_image"]
    inlines = (TagInline,)
    list_filter = (TagFilter, YearIsSetFilter)
    list_display = ('thumb_image', 'accession_number', 'year', 'caption')

    def thumb_image(self, obj):
        return mark_safe('<img src="{}" width="{}" height="{}" />'.format(obj.thumbnail.url, obj.thumbnail.width, obj.thumbnail.height))

    def h700_image(self, obj):
        return mark_safe('<img src="{}" width="{}" height="{}" />'.format(obj.h700.url, obj.h700.width, obj.h700.height))

class UserTagInline(admin.TabularInline):
    model = PhotoTag.creator.through
    extra = 0
    fields = ['thumb_image', 'tag', 'accepted']
    readonly_fields = ['thumb_image', 'tag', 'accepted']

    def thumb_image(self, instance):
        return mark_safe(
            '<a href="{edit_url}"><img src="{thumb}" width="{width}" height="{height}" /></a>'.format(
                edit_url=reverse('admin:archive_photo_change', args=(instance.phototag.photo.id,)),
                thumb=instance.phototag.photo.thumbnail.url,
                width=instance.phototag.photo.thumbnail.width,
                height=instance.phototag.photo.thumbnail.height,
            )
        )

    def tag(self, instance):
        return instance.phototag.tag.tag

    def accepted(self, instance):
        return 'yes' if instance.phototag.accepted else 'no'

class KronofotoUserAdmin(UserAdmin):
    inlines = (UserTagInline,)

admin.site.unregister(User)
admin.site.register(User, KronofotoUserAdmin)
