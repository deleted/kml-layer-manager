class Foo(object):
    payload = "some string"
    def __init__(self):
        print "My payload is: " + self.payload

print Foo.payload
f = Foo()
