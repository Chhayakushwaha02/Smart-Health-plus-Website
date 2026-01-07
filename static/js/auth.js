const toggleForm = document.getElementById("toggle-form");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const formTitle = document.getElementById("form-title");

toggleForm.onclick = () => {
    if (loginForm.style.display === "none") {
        loginForm.style.display = "flex";
        registerForm.style.display = "none";
        formTitle.innerText = "Login";
        toggleForm.innerText = "Don't have an account? Register";
    } else {
        loginForm.style.display = "none";
        registerForm.style.display = "flex";
        formTitle.innerText = "Register";
        toggleForm.innerText = "Already have an account? Login";
    }
};

// LOGIN
loginForm.onsubmit = async (e) => {
    e.preventDefault();
    const res = await fetch("/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            email: document.getElementById("login-email").value,
            password: document.getElementById("login-password").value
        })
    });
    const data = await res.json();
    if (data.success) window.location.href = "/dashboard";
    else document.getElementById("login-message").innerText = data.message;
};

// REGISTER
registerForm.onsubmit = async (e) => {
    e.preventDefault();
    const res = await fetch("/register", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            name: document.getElementById("reg-name").value,
            age: document.getElementById("reg-age").value,
            gender: document.getElementById("reg-gender").value,
            mobile: document.getElementById("reg-mobile").value,
            email: document.getElementById("reg-email").value,
            password: document.getElementById("reg-password").value,
            role: document.getElementById("reg-role").value
        })
    });
    const data = await res.json();
    document.getElementById("register-message").innerText = data.message;
    if (data.success) toggleForm.click();
};

// GOOGLE LOGIN
document.getElementById("google-login-btn").onclick = () => {
    alert("Google login not yet configured. Please contact admin.");
};

