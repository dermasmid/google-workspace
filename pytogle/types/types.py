class Scope:


    def __init__(self, scope_code, usage, description):
        self.scope_code = scope_code
        self.usage = usage
        self.description = description


    def __str__(self):
        return self.description

