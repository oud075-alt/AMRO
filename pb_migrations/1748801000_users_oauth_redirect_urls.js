/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("_pb_users_auth_")

  // Allow OAuth redirect back to the AMRO dashboard (different subdomain from PB).
  unmarshal({
    "authRedirectURLs": [
      "http://amroai.duckdns.org",
      "http://amroai.duckdns.org/",
      "https://amroai.duckdns.org",
      "https://amroai.duckdns.org/"
    ]
  }, collection)

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("_pb_users_auth_")

  unmarshal({
    "authRedirectURLs": []
  }, collection)

  return app.save(collection)
})
