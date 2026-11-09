import assert from "node:assert/strict"

const origin = process.argv[2] || "http://localhost:3002"
for (const path of ["/dev/states/ready", "/chat/a-place-to-think", "/projects/skye-web"]) {
  const response = await fetch(`${origin}${path}`)
  assert.equal(response.status, 404, `${path} must not expose development fixtures`)
}
const html = await (await fetch(`${origin}/chat`)).text()
assert(!html.includes("A quieter week"), "Production navigation contains fixture data")
assert(!html.includes("Interface preview"), "Production navigation advertises fixture routes")
assert.equal((await fetch(`${origin}/api/v1/spike/events`)).status, 404, "Lab rewrite must be absent")
console.log("Production preview routes, sample navigation and lab rewrite are disabled.")
