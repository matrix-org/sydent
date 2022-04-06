# Templates

Sydent uses parametrised templates to generate the content of emails it
sends and webpages it shows to users. Example templates can be found in
the [res](https://github.com/matrix-org/sydent/tree/main/res) folder.

## Branding

Sending a value for `brand` to some API endpoints allows for different
email and http templates to be used. These templates should be stored
in a file structure like this:

```
 root_template_dir/
     brand1/
         [ brand1 template files ]
     brand2/
         [ brand2 template files ]
```

The config option `templates.root_directory` should be set to the path
of `root_template_dir` and `templates.default_brand` should be set to
the sub directory to use if no `brand` (or an invalid `brand`) is provided
by the request.

Here are the requests that can contain a value for `brand` and what
template the brand value is used to select:

Invite email templates:
 - ` POST /_matrix/identity/v1/store-invite`
 - ` POST /_matrix/identity/v2/store-invite`

Verification email templates:
 - `POST /_matrix/identity/v1/validate/email/requestToken`
 - `POST /_matrix/identity/v2/validate/email/requestToken`

Verification SMS templates - BRAND CURRENTLY IGNORED:
 - `POST /_matrix/identity/v1/validate/msisdn/requestToken`
 - `POST /_matrix/identity/v2/validate/msisdn/requestToken`

Verification response templates:
 - `GET /_matrix/identity/v1/validate/email/submitToken`
 - `GET /_matrix/identity/v2/validate/email/submitToken`

 - `GET /_matrix/identity/v1/validate/msisdn/submitToken`
 - `GET /_matrix/identity/v2/validate/msisdn/submitToken`


## Template formats

### `.eml.j2` files

Files ending in ".eml.j2" are Jinja templates. 

Using the `urlencode` Jinja filter encodes the contents for URLs suitably.
All variables are automatically made safe for HTML.

If needed the `safe` filter can be used to prevent the HTML encoding, this is
useful for email headers and for including a plaintext portion of an email.

See the Jinja [documentation](https://jinja.palletsprojects.com/en/3.0.x/templates/#variables)
for more instructions on how to write these templates.

### DEPRECATED `.eml` template files 

Files ending in ".eml" can use python `%(variable)s` string substitution.

Appending "_forurl" or "_forhtml" to any of the variable names listed below
returns their values encoded suitably for URLs or HTML respectively.

For example ">" in the `_forhtml` version would be replaced with "&gt".

Note: "&&" must be used to get a raw `&` character.

---


## Invite email templates 

Invitation emails are sent when someone is invited to a room by their
email address. They should contain a link for the user to click on
that takes them to a matrix client.

Invite template files should have the name `invite_template.eml.j2`.

### Substitutions from Sydent

Variable                | Contents 
-----------             | -------- 
`date`                  | The time and date of sending as defined in RFC 2822 (e.g. "Fri, 09 Nov 2001 01:08:47 -0000") 
`ephemeral_private_key` | The ephemeral private key being used for this invite
`from`                  | The sending email address as configured in `email.from`
`messageid`             | The unique ID for this email 
`multipart_boundary`    | Randomized multipart boundary to use in multipart emails. **NOTE: has no `_forurl` or `_forhtml` variants**
`subject_header_value`  | The invite subject line. As configured in `email.invite.subject` (for a room invite) and `email.invite. subject_space` (for a space invite)
`to`                    | The destination email address 
`token`                 | A randomly generated token 
`web_client_location`   | Default web client to invite user to join via

### Substitutions from homeservers

All values that get sent to the `/_matrix/identity/v2/store-invite` API 
endpoint are accessible as variables in invite templates.

Invites sent from Synapse make the following available:

Variable                | Contents 
-----------             | -------- 
`address`               | The email address being invited (same as `to`)
`bracketed_room_name`   | The string stored in `room_name` with brackets around it
`bracketed_verified_sender`      | The string stored in `sender` with brackets around it
`medium`                | The string "email"
`org.matrix.web_client_location` | **UNSTABLE.** The same as `web_client_location`
`room_alias`            | An alias for the room (probably more readable than `room_id`)
`room_avatar_url`       | The URL of the room's avatar
`room_id`               | The ID of the room to which the user is invited
`room_join_rules`       | The join rules of the email (e.g. "public" or "invite")
`room_name`             | The m.room.name state of the room. (e.g. "Synape Admins")
`room_type`             | Is set to "m.space" if the invite is to a space
`sender`                | The user ID of the inviter
`sender_avatar_url`     | The URL of the inviter's avatar
`sender_display_name`   | The current display name of the inviter

Version when table last updated: Synapse v1.42.0


## Verification email templates

Verification template files should have the name `verification_template.eml.j2`.

### All substitutions

Variable                | Contents 
-----------             | -------- 
`date`                  | The time and date of sending as defined in RFC 2822 (e.g. "Fri, 09 Nov 2001 01:08:47 -0000") 
`from`                  | The sending email address as configured in `email.from`
`ipaddress`             | The IP address that the verification request came from. If the IP address is unknown then this is the string "an unknown location"
`messageid`             | The unique ID for this email 
`multipart_boundary`    | Randomized multipart boundary to use in multipart emails. **NOTE: has no `_forurl` or `_forhtml` variants**
`to`                    | The destination email address 
`token`                 | A randomly generated token that some clients might need


## Verification SMS templates

The SMS template isn't read from a file. Instead the SMS template
should be placed as a string into the config option `bodyTemplate`.

This string uses python `{variable}` substitution.

### All substitutions

Variable    | Contents 
----------- | -------- 
`token`     | A randomly generated token for the user to enter into the client


## Migration email templates

Migration template files should have the name `migration_template.eml.j2`.
The deprecated `.eml` template version is not supported.

### All substitutions

Variable                | Contents 
-----------             | -------- 
`date`                  | The time and date of sending as defined in RFC 2822 (e.g. "Fri, 09 Nov 2001 01:08:47 -0000") 
`from`                  | The sending email address as configured in `email.from`
`messageid`             | The unique ID for this email 
`multipart_boundary`    | Randomized multipart boundary to use in multipart emails. **NOTE: has no `_forurl` or `_forhtml` variants**
`mxid`                  | The user ID that has been disassociated from the destination email address
`to`                    | The destination email address 


## Verification response http templates

Verification response templates should have the name `verify_response_template.http`.

### All substitutions

Variable                | Contents 
-----------             | -------- 
`message`               | The verification success or failure message from the server
