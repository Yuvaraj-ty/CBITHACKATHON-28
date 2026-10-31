// Front-end login form: collects input and posts it to /login.
const form = document.querySelector("#login-form");

function readForm(formEl) {
  const data = new FormData(formEl);
  return { email: data.get("email"), password: data.get("password") };
}

function showError(message) {
  const box = document.querySelector("#error");
  box.textContent = message;
  box.hidden = false;
}

async function submitLoginForm(event) {
  event.preventDefault();
  const payload = readForm(form);
  if (!payload.email || !payload.password) {
    showError("Email and password are required");
    return;
  }
  const res = await fetch("/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const body = await res.json();
  if (res.status !== 200) {
    showError(body.error);
    return;
  }
  localStorage.setItem("token", body.token);
  window.location.href = "/dashboard";
}

form.addEventListener("submit", submitLoginForm);
