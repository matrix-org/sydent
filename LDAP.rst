LDAP configuration
==================

If you don't need LDAP
----------------------

If ``uri`` parameter is not specified in the ``[ldap]`` config section, LDAP functional will be skipped.

Purpose
-------
LDAP configuration allow perform ldap lookup for matrix id by mail address.

The addresses found in the LDAP address do not need to be assigneed and verified: it is assumed that the LDAP is a trusted store.

Other third party ids (that not found in LDAP) can be assigned and verifed classical way (they will be saved to the database)

Example LDAP config section
---------------------------

.. code:: 

    [ldap]
    uri = ldap://example.com:389/
    startls =  false
    base = dc=example,dc=com
    mail_attr = mail
    id_attr = samaccountname
    # if hs_name empty we assume that id_attr contain users matrix id
    # othercase we generate matrix id as @id_attr:hs_name
    hs_name = example.com
    bind_dn = cn=namager,cn=users,dc=example,dc=com
    bind_pw = secret
    filter = (&(objectClass=user)(objectCategory=person))

