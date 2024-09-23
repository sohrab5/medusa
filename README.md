# Medusa
Turn dynamic websites into static stones!

There are many "dynamic" websites on the internet (meaning they need Apache, PHP, MySQL etc on the backend) just so they can display a few completely static and unchanging HTML pages to the visitors of the website. Probably most Wordpress websites fall under this category.

So one day I had the brilliant idea: let's get rid of that bloat of PHP, MySQL etc and transform the whole backend of such websites into the holy grail of all web serving: only static HTML files + Nginx!

Medusa is a single file python script designed to crawl a website recursively and fetch all the pages, download all the static assets (including static assets defined in CSS files and HTML style tags), and turn each page on the domain being crawled into a static HTML file suitable for serving. Resulting HTML files and static assets can be built into a self contained minimal Nginx Docker image ready to run with no additional run-time configuration.

You give away all server-side dynamic functionality and in return you gain maximum performance at a fraction of server cost, maximum backend security and a completely maintenance free setup.

Yes there might be a dynamic admin panel or CMS of sorts on the backend with which the site admin updates the content on the website. It might even be argued that said admin panel is the main point of frameworks like Wordpress. And all of that functionality will be lost here. But we're not concerned with that here. Medusa only cares about the end results of such frameworks: The publicly accessible "front" of the website, which the actual users visit, and is static from the point of view of users.

Note that the words "dynamic" and "static" only refer to server-side functionality in this document. Javascript for frontend-side things will be served to the users without any modification, like any other static asset.

If you want to retain such dynamic admin panels for your website, you might want to keep running the PHP website somewhere privately as a staging area, so it's updatable from its admin panel. Then run Medusa on it to create a static snapshot of the website and then serve the resulting snapshot on your production servers, under any other domain name, using a fraction of the resources the dynamic website needs for real traffic.

The performance improvements are very significant. And it should be pretty obvious. You can serve several orders of magnitude more requests per second using a pure Nginx + HTML files setup than you could if you were serving the whole dynamic PHP website using the same hardware. Every page of the website loads as fast and snappy as possible. Users are happy and search engines are happy!

Security improvements should be obvious as well. If there are no complex machinery like PHP etc on the backend, there is simply nothing to do on the server except serving static files. You're as secure as the latest stable version of Nginx serving static public files, which is pretty much as secure as you can get! Also because of the massive performance improvements you'll get, your website becomes much more resistant against DDoS attacks at no additional cost as well.

### Relative URLs

By default, all absolute URLs on the same domain being crawled are converted into relative URLs so the resulting HTML files could be served on any other domain, completely untethered from the original domain.

For example if we're crawling `https://example.com` and somewhere on any of the pages there are tags like below:
```html
<a href="https://example.com/foo"><img src="https://example.com/assets/pic.jpg"></a>
```
They will be converted to the following in the resulting HTML file:
```html
<a href="/foo"><img src="/assets/pic.jpg"></a>
```
Links to other domains will of course remain unchanged. They will not be scraped by Medusa either.

If you really want to have absolute links, use the option `--absolute-url` and supply the URL to prefix the links.

In addition to supporting absolute URLs like mentioned above, Medusa supports crawling websites that use relative URLs as well. For example links such as `/foo`, `./foo`, `../foo`, `//foo`, `foo` are understood, resolved and scraped, based on the address of the page they were found on.

### Installing dependencies

The only dependency beside python standard library is [pycurl](https://pypi.org/project/pycurl/)

Run the following to install it system-wide:

- Debian / Ubuntu
```
apt install python3-pycurl
```
- Arch Linux
```
pacman -S python-pycurl
```
- Alpine Linux
```
apk add py3-curl
```

### Running the script
Clone this repository and cd into it. Static files will be downloaded in the current working directory.
```
git clone https://github.com/sohrab5/medusa.git
cd medusa
```
Run the script, giving the root URL of the website you want to make static as the command line argument.

```
python3 medusa.py https://example.com
```
You can exclude any path that you don't want to be crawled using `-s` or `--skip` flag. In the following example any page on example.com that has `/blog` in it's path will be skipped:
```
python3 medusa.py -s=/blog https://example.com
```
The following example will produce clean results on most typical Wordpress websites:
```
python3 medusa.py -s='?p=' -s=json -s=xmlrpc https://mywordpresswebsite.com
```
When the script is finished running, we can build a self contained Docker image of the whole website:
```
docker build --build-arg WEBROOT_DIR=example.com_files --build-arg NGINX_CONFS_DIR=example.com_nginx_confs -t example.com-static-website:2024-08-25T16-32 .
```
(`example.com_files` and `example.com_nginx_confs` in the example above are directories created by Medusa after running it on `https://example.com`)

Running the Docker container is trivial:
```
docker run -d -p 80:80 example.com-static-website:2024-08-25T16-32
```
Note that the provided nginx.conf only listens on port 80 and doesn't do TLS termination. If you want to do TLS termination inside this container add your certs and relevant nginx directives to nginx.conf.

In general things are kept as simple and bare bones as possible so it can be used as the base for any further customizations needed. This applies to the generated HTML files as well. The script tries to do a complete job, but you also have a text editor! You can (or might have to) edit them manually before building the final image.

### Known bugs and limitations

Currently the URL for the website to be crawled has to be the root URL and we can't start at a sub path. For example `https://site.example.com` is a valid root URL argument but `https://site.example.com/some-path` is not.

We can start at the root of the website and skip unwanted paths like mentioned above to kind of get around this.

Also the script is regex based and doesn't use heavy parsing libraries for HTML and CSS. That means there might be corner cases in those standards that won't function properly here. I'd appreciate a bug report if you spot any valid HTML/CSS on a source website that is not working correctly on the static version of it. That said the common ways of writing HTML and CSS that majority of websites use are supported and tested.

### Disclaimer

The code is released under the GPL license and you are free to do what you want with it under the terms of that license. That said I obviously don't condone scraping websites you don't own or serving them as your own for any malicious or shady purpose. The intended use case is that you already own a Wordpress or similar website, and you want to make it a lot faster, a lot more robust with far fewer moving parts.
