from django.views.generic import ListView
from django.contrib.auth.models import User


class UserListView(ListView):
    model = User
    context_object_name = 'user_list'

    def get_context_data(self, **kwargs):
        context = super(UserListView, self).get_context_data(**kwargs)
        context['request'] = self.request
        return context
