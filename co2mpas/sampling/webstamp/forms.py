from flask_wtf import FlaskForm
import json
import logging
import os
from pprint import pformat
import re

from flask import flash, request, session
import flask
from flask.ctx import after_this_request
from markupsafe import escape, Markup
from ruamel import yaml
from validate_email import validate_email
import wtforms

import textwrap as tw
import wtforms.fields as wtff
import wtforms.fields.html5 as wtf5
import wtforms.validators as wtfl


STAMPED_PROJECTS_KEY = 'stamped_projects'

def create_stamp_form_class(app):
    ## Prepare various config-dependent constants

    config = app.config
    client_validation_log_full_dreport = config['CLIENT_VALIDATION_LOG_FULL_DREPORT']
    client_validation_log_level = config['CLIENT_VALIDATION_LOG_LEVEL']
    try:
        client_validation_log_level = int(client_validation_log_level)
    except:  # @IgnorePep8
        client_validation_log_level = logging._nameToLevel.get(
            client_validation_log_level, logging.DEBUG)


    def get_json_item(adict, key, *, as_list):
        json_type = list if as_list else dict
        cookie_value = adict.get(key)
        if cookie_value:
            try:
                cookie_value = json.loads(cookie_value)
                if isinstance(cookie_value, json_type):
                    return cookie_value

                app.logger.info("Expected JSON(%s) to be %s, it was: %s"
                                "\n  COOKIE=%s",
                                key, json_type.__name__,
                                type(cookie_value), cookie_value)
            except json.JSONDecodeError as ex:
                app.logger.info("Corrupted JSON(%s) due to: %s"
                                "\n  \n  COOKIE==%s",
                                key, ex, cookie_value,
                                exc_info=1)

        return json_type()


    def get_stamped_projects(cookies):
        return set(get_json_item(cookies, STAMPED_PROJECTS_KEY, as_list=True))


    def is_project_stamped(cookies, project):
        return project in get_stamped_projects(cookies)


    def add_project_as_stamped(cookies, project):
        stamped_projects = get_stamped_projects(cookies)
        stamped_projects.add(project)
        stamped_projects = list(sorted(set(stamped_projects)))

        @after_this_request
        def store_stamped_projects(response):
            response.set_cookie(STAMPED_PROJECTS_KEY, json.dumps(stamped_projects))
            return response


    class StampForm(FlaskForm):

        _skeys = 'dice_stamp stamp_recipients dice_decision'.split()

        stamp_recipients = wtff.TextAreaField(
            label='Stamp Recipients:',
            description="(separate email-addresses by <kbd>,</kbd>, <kbd>;</kbd>, "
            "<kbd>[Space]</kbd>, <kbd>[Enter]</kbd>, <kbd>[Tab]</kbd> characters)",
            validators=[wtfl.InputRequired()],
            default=config.get('DEFAULT_STAMP_RECIPIENTS'),
            render_kw={'rows': config['MAILIST_WIDGET_NROWS']})

        dice_report = wtff.TextAreaField(
            # label='Dice Report:',  Set in `_manage_session()`.
            render_kw={'rows': config['DREPORT_WIDGET_NROWS']})

        submit = wtff.SubmitField(
            'Stamp!',
            description=" This action is irreversible!",
            render_kw={})

        def validate_email_list(self, field):
            text = field.data
            check_mx = os.name != 'nt'

            mails = re.split('[\s,;]+', text)
            mails = [s and s.strip() for s in mails]
            mails = list(filter(None, mails))
            for i, email in enumerate(mails, 1):
                if not validate_email(email, check_mx=check_mx):
                    raise wtforms.ValidationError(
                        'Invalid email-address no-%i: `%s`' % (i, email))

            return mails

        def validate_dice_report(self, field):
            min_dreport_size = config['MIN_DREPORT_SIZE']
            data = field.data and field.data.strip()
            if not data:
                raise wtforms.ValidationError("Dice-report is required.")
            if len(data) < min_dreport_size:
                raise wtforms.ValidationError(
                    "Dice-report is too short (less than %s char)." %
                    min_dreport_size)

            return data

        def _log_client_errors(self):
            dreport = '<hidden>'
            if client_validation_log_full_dreport:
                dreport = self.dice_report.data
                if dreport and client_validation_log_full_dreport is not True:
                    dreport = '%s\n...\n%s' % (
                        dreport[:client_validation_log_full_dreport],
                        dreport[-client_validation_log_full_dreport:])
            if app.logger.isEnabledFor(client_validation_log_level):
                indent = ' ' * 4
                app.logger.log(
                    client_validation_log_level,
                    tw.dedent("""
                        CLient validation-errors while Stamping:
                          stamp_recipients:
                        %s
                          dice_report:
                        %s
                          errors:
                        %s
                    """),
                    tw.indent(self.stamp_recipients.data, indent),
                    tw.indent(dreport, indent),
                    tw.indent(pformat(self.errors), indent))

        def _manage_session(self, is_stamped):
            """If `is_stamped`, disable & populate fields from session, else clear it."""
            if is_stamped:
                dice_stamp, stamp_recipients, dice_decision = [session[k]
                                                               for k in self._skeys]
                self.dice_report.data = dice_stamp
                self.stamp_recipients.data = stamp_recipients
                dreport_label = "Dice Report <em>Stamped</em>:"
                flash(Markup("<em>Dice-stamp</em> sent to %i recipient(s): %s"
                             "<br>Decision:<pre>\n%s</pre>" %
                             (len(stamp_recipients),
                              escape('; '.join(stamp_recipients)),
                              escape(yaml.dump(dice_decision,
                                               default_flow_style=False)))))
            else:
                dreport_label = "Dice Report:"
                for k in self._skeys:
                    session.pop(k, None)

            form_disabled = is_stamped
            self.stamp_recipients.render_kw['readonly'] = form_disabled
            self.dice_report.render_kw['readonly'] = form_disabled
            self.submit.render_kw['disabled'] = form_disabled
            self.dice_report.label.text = dreport_label

        def _sign_dreport(self, dreport):
            # TODO: stamp!
            from random import choices

            dice_stamp = '#### STAMPED!\n%s' % dreport[:200]
            dice_decision = dict(sender='sender-%s' % choices(range(3)),
                           project='project-%s' % choices(range(3)))

            return dice_stamp, dice_decision

        def _do_stamp(self):
            from co2mpas.sampling import CmdException

            stamp_recipients = self.validate_email_list(self.stamp_recipients)
            dreport = self.validate_dice_report(self.dice_report)

            try:
                dice_stamp, dice_decision = self._sign_dreport(dreport)
            except CmdException as ex:
                app.logger.info("Stamp-signing denied due to: %s", ex, exc_info=1)
                flash(str(ex), 'error')
            except Exception as ex:
                app.logger.info("Stamp-signing failed due to: %s", ex, exc_info=1)
                flash(Markup("Stamp-signing failed due to: %s(%s)"
                      "<br>  Contact JRC for help." % (type(ex).__name__, ex)),
                      'error')
            else:
                project = dice_decision['project']

                if is_project_stamped(request.cookies, project):
                    flash(Markup("You have <em>diced</em> project %r before!"
                          "<br>Repeat dice??" %
                          project), 'error')
                else:
                    session.update(zip(self._skeys,
                                       [dice_stamp, stamp_recipients, dice_decision]))
                    flash(Markup(
                        "Import the <em>dice-stamp</em> above into your project."))
                    add_project_as_stamped(request.cookies, project)
                    self._manage_session(True)

        def render(self):
            if not self.is_submitted():
                ## Clear session.
                self._manage_session(False)
            else:
                if 'dice_stamp' in session:
                    flash("Already diced! Click 'New stamp...' above.", 'error')
                    self._manage_session(True)
                else:
                    if self.validate():
                        self._do_stamp()
                    else:
                        self._log_client_errors()

            return flask.render_template('stamp.html', form=self)

    return StampForm  # class
