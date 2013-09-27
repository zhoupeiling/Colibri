#!/bin/env python
# -*- coding: utf-8
#

#    Copyright (C) 2008-2011 Thomas Capricelli <orzel@freehackers.org>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header, decode_header

def create_outbound_message(m, mylist, boundary=None, boundary_embedded=None):
    """
    This method is outside of class Colibrid so that it can be tested
    boundary and boundary_embedded should only be provided when testing

    Details on all mail headers
    http://people.dsv.su.se/~jpalme/ietf/ietf-mail-attributes.html

    >>> list = FakeList()
    >>> testOneFile(list, "testdata/simple.input.txt", "testdata/output.notrailer/simple.txt")
    True
    >>> testOneFile(list, "testdata/alternative.input.txt", "testdata/output.notrailer/alternative.txt")
    True
    >>> list = FakeList(trailer="asdfasdf")
    >>> testOneFile(list, "testdata/simple.input.txt", "testdata/output.trailer/simple.txt")
    True
    >>> testOneFile(list, "testdata/alternative.input.txt", "testdata/output.trailer/alternative.txt")
    True
    >>> testOneFile(list, "testdata/input2.txt", "testdata/output2.txt") # doesn't exist
    error while reading testdata/input2.txt
    False
    """
    #
    # First we deal with the message content
    #
    if mylist.trailer!="" or mylist.header!="":
        # we need to create a multipart
        mail = MIMEMultipart(boundary=boundary)

        # copy some headers
        #raise ValueError(", ".join([h[0] for h in m.items()])) # <- this can be used to know which headers are considered
        for h in m.items():
            # only copy some of them:
            if h[0] not in ["From", "Organization", "To", "Subject", "Date", ]:
                continue
            mail.add_header(h[0],h[1])
        # header", if any
        if mylist.header!="":
            header = MIMEText(mylist.header, 'plain', 'utf8')
            header.add_header('Content-Disposition', 'inline')
            mail.attach(trailer)

        # original content
        if m.is_multipart():
            # embed previous mail, removing headers
            embedded = MIMEMultipart(_subtype=m.get_content_subtype(), boundary=boundary_embedded)
            for part in m.get_payload():
                embedded.attach(part)
            mail.attach(embedded)
        else:
            # just copy the text
            mail.attach( MIMEText(m.get_payload(), 'plain', m.get_content_charset()))

        # trailer, if any
        if mylist.trailer!="":
            trailer = MIMEText(mylist.trailer, 'plain', 'utf8')
            trailer.add_header('Content-Disposition', 'inline')
            mail.attach(trailer)
    else:
        mail = m

    #
    # Now we deal with headers
    #

    # change the subject if needed
    if mylist.subject_tag != '':
        tag = '['+ mylist.subject_tag + '] '
        header_parts = decode_header(mail['Subject'])
        subject = " ".join([subject.decode(charset) if charset is not None else subject for subject,charset in header_parts])
        if mylist.subject_tag not in subject:
            del mail['Subject']
            mail['Subject'] = Header(tag + subject, 'utf-8')

    # add some headers
    mail['List-Software'] = u"Colibri http://labs.freehackers.org/projects/colibri/wiki"
    if mylist.include_author_in_reply_to:
        mail['Reply-To'] = u"%s,%s" % (unicode(mylist), m['From'])
    else:
        mail['Reply-To'] = unicode(mylist)
    mail['X-Loop'] = unicode(mylist)
    mail['Precedence'] = u"list"
    mail['X-no-archive'] = u"yes"
    mail['List-Post'] = u"<mailto:%s>"% unicode(mylist)
    mail['List-Owner'] = u"<mailto:%s>" % mylist.list_address_extended('request')
    mail['List-Id'] = u"<%s>" % mylist.list_id()
    mail['Errors-to'] = mylist.list_address_extended('owner')
# TODO
#    mail['List-Help'] = u"<mailto:colibri@freehackers.org?subject=help>"
#    mail['List-Subscribe'] = u"<mailto:colibri@freehackers.org?subject=subscribe%20annexe>"
#    mail['List-Unsubscribe'] = u"<mailto:colibri@freehackers.org?subject=unsubscribe%20annexe>"
#    mail['List-Archive'] = u"<https://secure.freehackers.org/wws/arc/annexe>"
#    mail['X-Sequence'] = u"13927"
    return mail

#
# Tests
#
from email.parser import Parser
testparser = Parser()

class FakeList():
    """
    Fake object behaving like django model "List"
    """
    def __init__(self, name="fakelist", host="fakehost.org", header="", trailer="", tag="fakelist", include_author=False):
        self.name = name
        self.host = host
        self.header = header
        self.trailer = trailer
        self.subject_tag = tag
        self.include_author_in_reply_to = include_author
    def list_address_extended(self, extension):
        """ Return a string in the form <name>-<extension>@<host>, where
        extension is given as first argument """
        return u"%s-%s@%s" % (self.name, extension, self.host)
    def list_id(self):
        """
        return the string suitable for 'List-Id' in mail header
        """
        return u"%s.%s" % (self.name, self.host)
    def __unicode__(self):
        return u"%s@%s" % (self.name, self.host)

def testOneFile(list, inputfilename, outputfilename):
    # get input
    try:
        inputmail = testparser.parse(file(inputfilename, 'r'))
    except:
        print "error while reading", inputfilename
        return False

    # create output
    outputmail = create_outbound_message(inputmail, list, boundary="===============4463115622804793711==", boundary_embedded="Boundary-01=_IfjBNvTks4QPuES").as_string()
    #outputmail = create_outbound_message(inputmail, list).as_string()

    # test
    try:
        f = open(outputfilename, 'r')
        refmail = f.read()
        f.close()
    except:
        print "error while reading", outputfilename
        return False
        return False
    if refmail != outputmail:
        from subprocess import call
        print "Test failed. Actual output in outputmail.txt, diff follows:"
        print "Command is : diff -u %s outputmail.txt\n\n" % outputfilename
        f = open("outputmail.txt", "w")
        f.write(outputmail)
        f.close()
        call(['diff', '-u', outputfilename, "outputmail.txt"])
        return False
    return True

if __name__ == '__main__':
    import doctest
    doctest.testmod()
