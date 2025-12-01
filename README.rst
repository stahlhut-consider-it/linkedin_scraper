.. role:: raw-html-m2r(raw)
   :format: html


Linkedin Scraper
================

Scrapes Linkedin person data.

`Linkedin Scraper <#linkedin-scraper>`_


* `Installation <#installation>`_
* `Setup <#setup>`_
* `Usage <#usage>`_

  * `Sample Usage <#sample-usage>`_
  * `Person Scraping <#person-scraping>`_
  * `Scraping sites where login is required first <#scraping-sites-where-login-is-required-first>`_
  * `Scraping sites and login automatically <#scraping-sites-and-login-automatically>`_

* `API <#api>`_

  * `Person <#person>`_

    * `\ ``linkedin_url`` <#linkedin_url>`_
    * `\ ``name`` <#name>`_
    * `\ ``about`` <#about>`_
    * `\ ``experiences`` <#experiences>`_
    * `\ ``educations`` <#educations>`_
    * `\ ``interests`` <#interests>`_
    * `\ ``accomplishment`` <#accomplishment>`_
    * `\ ``company`` <#company>`_
    * `\ ``job_title`` <#job_title>`_
    * `\ ``driver`` <#driver>`_
    * `\ ``scrape`` <#scrape>`_
    * `\ ``scrape(close_on_complete=True)`` <#scrapeclose_on_completetrue>`_

* `Contribution <#contribution>`_

Installation
------------

.. code-block:: bash

   pip3 install --user linkedin_scraper

Version **2.0.0** and before is called ``linkedin_user_scraper`` and can be installed via ``pip3 install --user linkedin_user_scraper``

Setup
-----

`zendriver <https://zendriver.dev/>`_ is used to launch and control Chrome via the DevTools protocol, so no separate ChromeDriver binary is required. Provide a ``user_data_dir`` in the config if you want to reuse an existing Chrome profile.


Usage
-----

To use it, just create the class.

Sample Usage
^^^^^^^^^^^^

.. code-block:: python

   import asyncio
   from linkedin_scraper import Person, actions


   async def main():
       browser = await actions.start_browser(actions.build_browser_config())
       tab = await browser.get("https://www.linkedin.com/")
       tab = await actions.login(tab, "some-email@email.address", "password123")
       person = Person("https://www.linkedin.com/in/joey-sham-aa2a50122", driver=tab, close_on_complete=False)
       print(person)
       await browser.stop()


   if __name__ == "__main__":
       asyncio.run(main())

**NOTE**\ : The account used to log-in should have it's language set English to make sure everything works as expected.

Person Scraping
^^^^^^^^^^^^^^^

.. code-block:: python

   from linkedin_scraper import Person
   person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5")

Scraping sites where login is required first
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


#. Run ``ipython`` or ``python``
#. In ``ipython``\ /\ ``python``\ , run the following code (you can modify it if you need to specify your driver)
#. 
   .. code-block:: python

      from linkedin_scraper import Person
      person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5", scrape=False)

#. Login to Linkedin
#. [OPTIONAL] Logout of Linkedin
#. In the same ``ipython``\ /\ ``python`` code, run
   .. code-block:: python

      person.scrape()

The reason is that LinkedIn has recently blocked people from viewing certain profiles without having previously signed in. So by setting ``scrape=False``\ , it doesn't automatically scrape the profile, but Chrome will open the linkedin page anyways. You can login and logout, and the cookie will stay in the browser and it won't affect your profile views. Then when you run ``person.scrape()``\ , it'll scrape and close the browser. If you want to keep the browser on so you can scrape others, run it as 

**NOTE**\ : For version >= ``2.1.0``\ , scraping can also occur while logged in. Beware that users will be able to see that you viewed their profile.

.. code-block:: python

   person.scrape(close_on_complete=False)

so it doesn't close.

Scraping sites and login automatically
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

From verison **2.4.0** on, ``actions`` is a part of the library that allows signing into Linkedin first. The email and password can be provided as a variable into the function. If not provided, both will be prompted in terminal.

.. code-block:: python

   import asyncio
   from linkedin_scraper import Person, actions


   async def main():
       browser = await actions.start_browser(actions.build_browser_config())
       tab = await browser.get("https://www.linkedin.com/")
       tab = await actions.login(tab, "some-email@email.address", "password123")
       person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5", driver=tab, close_on_complete=False)
       print(person)
       await browser.stop()


   if __name__ == "__main__":
       asyncio.run(main())

API
---

Person
^^^^^^

A Person object can be created with the following inputs:

.. code-block:: python

   Person(linkedin_url=None, name=None, about=[], experiences=[], educations=[], interests=[], accomplishments=[], company=None, job_title=None, driver=None, scrape=True)

``linkedin_url``
~~~~~~~~~~~~~~~~~~~~

This is the linkedin url of their profile

``name``
~~~~~~~~~~~~

This is the name of the person

``about``
~~~~~~~~~~~~~

This is the small paragraph about the person

``experiences``
~~~~~~~~~~~~~~~~~~~

This is the past experiences they have. A list of ``linkedin_scraper.objects.Experience``

``educations``
~~~~~~~~~~~~~~~~~~

This is the past educations they have. A list of ``linkedin_scraper.objects.Education``

``interests``
~~~~~~~~~~~~~~~~~

This is the interests they have. A list of ``linkedin_scraper.objects.Interest``

``accomplishment``
~~~~~~~~~~~~~~~~~~~~~~

This is the accomplishments they have. A list of ``linkedin_scraper.objects.Accomplishment``

``company``
~~~~~~~~~~~~~~~

This the most recent company or institution they have worked at. 

``job_title``
~~~~~~~~~~~~~~~~~

This the most recent job title they have. 

``driver``
~~~~~~~~~~~~~~

This is the driver used to scrape the Linkedin profile. A ``zendriver`` tab is created by default. However, if a driver is passed in, that will be used instead.

For example

.. code-block:: python

   import asyncio
   from linkedin_scraper import Person, actions

   async def main():
       browser = await actions.start_browser(actions.build_browser_config())
       tab = await browser.get("https://www.linkedin.com/")
       person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5", driver = tab, close_on_complete=False)
       print(person)
       await browser.stop()

   asyncio.run(main())

``scrape``
~~~~~~~~~~~~~~

When this is **True**\ , the scraping happens automatically. To scrape afterwards, that can be run by the ``scrape()`` function from the ``Person`` object.

``scrape(close_on_complete=True)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the meat of the code, where execution of this function scrapes the profile. If *close_on_complete* is True (which it is by default), then the browser will close upon completion. If scraping of other profiles are desired, then you might want to set that to false so you can keep using the same driver.

Contribution
------------

:raw-html-m2r:`<a href="https://www.buymeacoffee.com/joeyism" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>`
