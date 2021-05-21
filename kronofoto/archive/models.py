from django.db.models import Q, Window, F, Min, Subquery, Count, OuterRef, Sum, Max
from django.urls import reverse
from django.db.models.functions import RowNumber
from django.db import models
from django.db.models.signals import post_delete, pre_delete
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.contrib.auth.models import User
import uuid
from PIL import Image, ExifTags, ImageOps
from io import BytesIO
import os
from functools import reduce
import operator
from bisect import bisect_left
from django.utils.http import urlencode
import hashlib
from django.http import QueryDict

class LowerCaseCharField(models.CharField):
    def get_prep_value(self, value):
        return str(value).lower()

class DonorQuerySet(models.QuerySet):
    def annotate_scannedcount(self):
        return self.annotate(scanned_count=Count('photos_scanned'))

    def annotate_donatedcount(self):
        return self.annotate(donated_count=Count('photo'))

    def filter_donated(self, at_least=1):
        return self.annotate_donatedcount().filter(donated_count__gte=at_least)

class Collectible:
    def get_absolute_url(self, params=None):
        return self.format_url(viewname='search-results', params=params)

    def get_embedded_url(self, params=None):
        return self.format_url(viewname='embedded-search-results', params=params)

    def format_url(self, viewname, params=None):
        if not params:
            params = QueryDict(mutable=True)
        return '{}?{}'.format(reverse(viewname), self.encode_params(params))

class Donor(Collectible, models.Model):
    last_name = models.CharField(max_length=256, blank=True)
    first_name = models.CharField(max_length=256, blank=True)
    home_phone = models.CharField(max_length=256, blank=True)
    street1 = models.CharField(max_length=256, blank=True)
    street2 = models.CharField(max_length=256, blank=True)
    city = models.CharField(max_length=256, blank=True)
    state = models.CharField(max_length=256, blank=True)
    zip = models.CharField(max_length=256, blank=True)
    country = models.CharField(max_length=256, blank=True)
    objects = DonorQuerySet.as_manager()

    class Meta:
        ordering = ('last_name', 'first_name')
        index_together = ('last_name', 'first_name')

    def __str__(self):
        return '{last}, {first}'.format(first=self.first_name, last=self.last_name) if self.first_name else self.last_name

    def encode_params(self, params):
        params['donor'] = self.id
        return params.urlencode()

    @staticmethod
    def index():
        return [
            {'name': '{last}, {first}'.format(last=donor.last_name, first=donor.first_name), 'count': donor.count, 'href': donor.get_absolute_url()}
            for donor in Donor.objects.annotate(count=Count('photo__id')).order_by('last_name', 'first_name').filter(count__gt=0)
        ]


class Collection(models.Model):
    PRIVACY_TYPES = [
        ('PR', 'Private'),
        ('UL', 'Unlisted'),
        ('PU', 'Public'),
    ]
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=512)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    visibility = models.CharField(max_length=2, choices=PRIVACY_TYPES)
    photos = models.ManyToManyField('Photo', blank=True)

    def get_absolute_url(self):
        return '{}?{}'.format(reverse('search-results'), urlencode({'query': 'collection:{}'.format(self.uuid)}))

    def __str__(self):
        return self.name


class Term(Collectible, models.Model):
    term = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(unique=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.term)
        super().save(*args, **kwargs)

    def encode_params(self, params):
        params['term'] = self.id
        return params.urlencode()

    @staticmethod
    def index():
        return [
            {'name': term.term, 'count': term.count, 'href': term.get_absolute_url()}
            for term in Term.objects.annotate(count=Count('photo__id')).order_by('term').filter(count__gt=0)
        ]

    def __str__(self):
        return self.term

class TagQuerySet(models.QuerySet):
    def __str__(self):
        return ', '.join(str(t) for t in self)

class Tag(Collectible, models.Model):
    tag = LowerCaseCharField(max_length=64, unique=True)
    slug = models.SlugField(unique=True, blank=True, editable=False)

    objects = TagQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.tag)
        super().save(*args, **kwargs)

    def encode_params(self):
        params = dict(tag=self.tag)
        if constraint:
            params['constraint'] = constraint
        return urlencode(params)

    @staticmethod
    def dead_tags():
        return Tag.objects.annotate(photo_count=Count('phototag')).filter(photo_count=0)

    @staticmethod
    def index():
        return [
            {'name': tag.tag, 'count': tag.count, 'href': tag.get_absolute_url()}
            for tag in Tag.objects.filter(phototag__accepted=True).annotate(count=Count('phototag__id')).order_by('tag')
        ]

    def __str__(self):
        return self.tag

    class Meta:
        ordering = ('tag',)

bisect = lambda xs, x: min(bisect_left(xs, x), len(xs)-1)

class PhotoQuerySet(models.QuerySet):
    def year_links(self, params=None):
        year_index = self.year_index()
        years = [p.year for p in year_index]
        year_range = Photo.objects.year_range()
        allyears = [(year, year_index[bisect(years, year)]) for year in range(year_range['start'], year_range['end']+1)]
        return [
            (year, photo.get_absolute_url(params=params), photo.get_json_url(params=params))
            for (year, photo) in allyears
        ]

    def year_index(self):
        set = Photo.objects.filter(id__in=Subquery(self.values('id')))
        yearid = set.values('year').annotate(min_id=Min('id'))
        yearcount = set.filter(year=OuterRef('year')).values('year').annotate(count=Count('id'))

        return set.filter(
            id__in=Subquery(yearid.values('min_id'))
        ).annotate(
            row_number=Window(
                expression=Sum(
                    Subquery(yearcount.values('count'), output_field=models.IntegerField())
                ),
                order_by=[F('year')],
            ) - Subquery(yearcount.values('count'), output_field=models.IntegerField())
        ).order_by('year')

    def year_range(self):
        return self.aggregate(end=Max('year'), start=Min('year'))

    def photo_position(self, photo):
        return self.filter(Q(year__lt=photo.year) | (Q(year=photo.year) & Q(id__lt=photo.id))).count()

    def filter_photos(self, collection):
        return collection.filter(self.filter(year__isnull=False, is_published=True))


def format_location(**kwargs):
    parts = []
    if kwargs.get('city', None):
        parts.append(kwargs['city'])
    if kwargs.get('county', None):
        parts.append('{} County'.format(kwargs['county']))
    if kwargs.get('state', None):
        parts.append(kwargs['state'])
    if not parts and kwargs.get('country', None):
        parts.append(kwargs['country'])
    s = ', '.join(parts)
    return s or 'Location: n/a'


class CollectionQuery:
    def __init__(self, expr, user):
        self.expr = expr
        self.user = user

    def filter(self, qs):
        if not self.expr:
            return qs.filter(year__isnull=False, is_published=True)
        if self.expr.is_collection():
            return self.expr.as_collection(qs, self.user)
        else:
            return self.expr.as_search(qs, self.user)

    def make_key(self, s):
        m = hashlib.md5()
        m.update(s.encode('utf-8'))
        return m.hexdigest()

    def cache_encoding(self):
        return self.make_key(repr(self.expr))

    def __str__(self):
        if not self.expr:
            return "All Photos"
        return str(self.expr.description())


class NewCutoff(models.Model):
    date = models.DateField()

    def save(self, *args, **kwargs):
        if not self.pk and NewCutoff.objects.exists():
            raise ValidationError('There can be only one instance of this object')
        return super().save(*args, **kwargs)

    def __str__(self):
        return 'Cutoff date for "new" photos'


class Photo(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    original = models.ImageField(null=True, editable=False)
    h700 = models.ImageField(null=True, editable=False)
    thumbnail = models.ImageField(null=True, editable=False)
    donor = models.ForeignKey(Donor, models.PROTECT, null=True)
    tags = models.ManyToManyField(Tag, blank=True, through="PhotoTag")
    terms = models.ManyToManyField(Term, blank=True)
    photographer = models.TextField(blank=True)
    city = models.CharField(max_length=128, blank=True, db_index=True)
    county = models.CharField(max_length=128, blank=True, db_index=True)
    state = models.CharField(max_length=64, blank=True, db_index=True)
    country = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    year = models.SmallIntegerField(null=True, blank=True, db_index=True)
    circa = models.BooleanField(default=False)
    caption = models.TextField(blank=True)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    scanner = models.ForeignKey(
        Donor, null=True, on_delete=models.SET_NULL, blank=True, related_name="photos_scanned"
    )

    objects = PhotoQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(is_published=False) | Q(donor__isnull=False), name="never_published_without_donor"),
        ]

    @classmethod
    def count(cls):
        return cls.objects.filter(is_published=True).count()

    def get_accepted_tags(self, user=None):
        filter_args = Q(phototag__accepted=True)
        if user:
            filter_args |= Q(phototag__creator__pk=user.pk)
        return self.tags.filter(filter_args).distinct()

    def save_params(self, params):
        self.params = params

    def get_proposed_tags(self):
        return self.tags.filter(phototag__accepted=False)

    def page_number(self, queryset=None):
        if hasattr(self, 'page'):
            return self.page.number
        if queryset:
            self.row_number = queryset.photo_position(self)
        if hasattr(self, 'row_number'):
            return self.row_number // 10 + 1
        raise AttributeError

    def add_params(self, url, params):
        if params:
            url = '{}?{}'.format(url, params.urlencode())
        return url

    def create_url(self, viewname, queryset=None, params=None):
        kwargs = {'photo': self.accession_number}
        try:
            kwargs['page'] = self.page_number(queryset=queryset)
        except AttributeError:
            pass

        url = reverse(
            viewname,
            kwargs=kwargs,
        )
        return self.add_params(url=url, params=params or hasattr(self, 'params') and self.params)

    def get_json_url(self, queryset=None, params=None):
        return self.create_url('photoview-json', queryset=queryset, params=params)

    def get_embedded_json_url(self, queryset=None, params=None):
        return self.create_url('embedded-photoview-json', queryset=queryset, params=params)

    def get_urls(self, embed=False):
        return {
            'url': self.get_embedded_url() if embed else self.get_absolute_url(),
            'json_url': self.get_embedded_json_url() if embed else self.get_json_url(),
        }

    def get_grid_url(self, params=None):
        page = self.row_number//settings.GRID_DISPLAY_COUNT + 1
        params = params or hasattr(self, 'params') and self.params
        if params:
            url = reverse('search-results')
            params = params.copy()
            params['page'] = page
        else:
            url = reverse('gridview')
        return self.add_params(url=url, params=params)


    def get_embedded_url(self, queryset=None, params=None):
        return self.create_url('embedded-photoview', queryset=queryset, params=params)

    def get_absolute_url(self, queryset=None, params=None):
        return self.create_url('photoview', queryset=queryset, params=params)

    def get_edit_url(self):
        return reverse('admin:archive_photo_change', args=(self.id,))

    @staticmethod
    def format_url(**kwargs):
        return "{}?{}".format(
            reverse('gridview'), urlencode(kwargs)
        )

    def get_county_url(self):
        return Photo.format_url(county=self.county, state=self.state)

    def get_city_url(self):
        return Photo.format_url(city=self.city, state=self.state)

    class CityIndexer:
        def index(self):
            return Photo.city_index()

    class CountyIndexer:
        def index(self):
            return Photo.county_index()

    @staticmethod
    def index_by_fields(*fields):
        return [
            {
                'name': ', '.join(p[field] for field in fields),
                'count': p['count'],
                'href': Photo.format_url(**{field: p[field] for field in fields}),
            }
            for p in Photo.objects.filter(
                is_published=True
            ).exclude(
                reduce(operator.or_, (Q(**{field: ''}) for field in fields))
            ).values(*fields).annotate(count=Count('id')).order_by(*fields)
        ]

    @staticmethod
    def county_index():
        return Photo.index_by_fields('county', 'state')

    @staticmethod
    def city_index():
        return Photo.index_by_fields('city', 'state')


    def __str__(self):
        return self.accession_number

    @staticmethod
    def accession2id(accession):
        if not accession.startswith('FI'):
            raise ValueError("{} doesn't start with FI", accession)
        return int(accession[2:])


    @property
    def accession_number(self):
        return 'FI' + str(self.id).zfill(7)

    def save(self, *args, **kwargs):
        if not self.thumbnail:
            Image.MAX_IMAGE_PIXELS = 195670000
            with ImageOps.exif_transpose(Image.open(BytesIO(self.original.read()))) as image:
                dims = ((75, 75), (None, 700))
                results = []
                w,h = image.size
                xoff = yoff = 0
                size = min(w, h)
                for dim in dims:
                    if any(dim):
                        img = image
                        if all(dim):
                            if w > h:
                                xoff = round((w-h)/2)
                            elif h > w:
                                yoff = round((h-w)/4)
                            img = img.crop((xoff, yoff, xoff+size, yoff+size))
                        if dim[0] and not dim[1]:
                            dim = (dim[0], round(h/w*dim[0]))
                        elif dim[1] and not dim[0]:
                            dim = (round(w/h*dim[1]), dim[1])
                        img = img.resize(dim, Image.ANTIALIAS)
                        results.append(img)
                thumb, h700 = results
                fname = 'thumb/{}.jpg'.format(self.uuid)
                thumb.save(os.path.join(settings.MEDIA_ROOT, fname), "JPEG")
                self.thumbnail.name = fname
                fname = 'h700/{}.jpg'.format(self.uuid)
                h700.save(os.path.join(settings.MEDIA_ROOT, fname), "JPEG")
                self.h700.name = fname
        super().save(*args, **kwargs)

    def location(self):
        kwargs = dict(
            city=self.city, state=self.state, county=self.county, country=self.country
        )
        if self.city:
            del kwargs['county']
        return format_location(**kwargs)


class WordCount(models.Model):
    FIELDS = [
        ('CA', 'Caption'),
        ('TA', 'Tag'),
        ('TE', 'Term'),
    ]
    photo = models.ForeignKey(Photo, models.CASCADE)
    word = models.CharField(max_length=64, blank=True, db_index=True)
    field = models.CharField(max_length=2, choices=FIELDS, db_index=True)
    count = models.FloatField()

    class Meta:
        index_together = [
            ('word', 'field')
        ]


class PhotoTag(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE)
    accepted = models.BooleanField()
    creator = models.ManyToManyField(User, editable=False)

def remove_deadtags(sender, instance, **kwargs):
    if instance.tag.phototag_set.count() == 0:
        instance.tag.delete()

def disconnect_deadtags(sender, instance, **kwargs):
    post_delete.disconnect(remove_deadtags, sender=Photo.tags.through)

def connect_deadtags(sender, instance, **kwargs):
    post_delete.connect(remove_deadtags, sender=Photo.tags.through)

post_delete.connect(remove_deadtags, sender=Photo.tags.through)
pre_delete.connect(disconnect_deadtags, sender=Tag)
post_delete.connect(connect_deadtags, sender=Tag)


class PrePublishPhoto(models.Model):
    id = models.AutoField(primary_key=True)
    photo = models.OneToOneField(Photo, on_delete=models.CASCADE)


class ScannedPhoto(models.Model):
    image = models.ImageField(upload_to='uploads/%Y/%m/%d/') # callable that incorporates donor name?
    donor = models.ForeignKey(Donor, models.PROTECT)

    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        Donor, null=True, on_delete=models.SET_NULL, related_name="scanned_photos"
    )
    accepted = models.BooleanField(null=True)


class PhotoVote(models.Model):
    photo = models.ForeignKey(ScannedPhoto, on_delete=models.CASCADE, related_name='votes', related_query_name='vote')
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    infavor = models.BooleanField()


class CSVRecord(models.Model):
    filename = models.TextField(unique=True)
    # unique constraint seems to make sense to me, but there are quite a few
    # duplicate records. should both be added? Or should we take newer added to
    # archive date to be the true record? Or should this be resolved on a case
    # by case basis?
    donorFirstName = models.TextField()
    donorLastName = models.TextField()
    year = models.IntegerField(null=True)
    circa = models.BooleanField(null=True)
    scanner = models.TextField()
    photographer = models.TextField()
    address = models.TextField()
    city = models.TextField()
    county = models.TextField()
    state = models.TextField()
    country = models.TextField()
    comments = models.TextField()
    added_to_archive = models.DateField()
    photo = models.OneToOneField(Photo, on_delete=models.SET_NULL, null=True)
