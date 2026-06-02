/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("_pb_users_auth_")

  // End users: email/password + must verify email before login token is issued.
  unmarshal({
    "passwordAuth": {
      "enabled": true,
      "identityFields": ["email"]
    },
    "authRule": "verified = true",
    "oauth2": {
      "enabled": true
    },
    "verificationTemplate": {
      "subject": "ยืนยันอีเมล AMRO",
      "body": "สวัสดี\n\nกรุณากดลิงก์ด้านล่างเพื่อยืนยันอีเมลและเข้าใช้งาน AMRO:\n\n{APP_URL}/_/#/auth/confirm-verification/{TOKEN}\n\nหากไม่ได้สมัคร ให้ละเว้นอีเมลนี้"
    }
  }, collection)

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("_pb_users_auth_")

  unmarshal({
    "passwordAuth": {
      "enabled": false,
      "identityFields": ["email"]
    },
    "authRule": "",
    "oauth2": {
      "enabled": true
    }
  }, collection)

  return app.save(collection)
})
