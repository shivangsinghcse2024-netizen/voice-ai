const $ = (id) => document.getElementById(id);

// ⚠️ PASTE YOUR GOOGLE CLIENT ID HERE:
const GOOGLE_CLIENT_ID = "695326698582-0m9ui4krohic95rmovnkv2661rpf8udm.apps.googleusercontent.com";

// Initialize real Google Sign-In on page load
window.onload = function () {
    if (typeof google !== 'undefined') {
        google.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            callback: handleCredentialResponse
        });

        // Renders the official Google button inside your index.html container
        const googleBtnContainer = $("google-login-container");
        if (googleBtnContainer) {
            google.accounts.id.renderButton(
                googleBtnContainer,
                { theme: "outline", size: "large", width: "100%" } 
            );
        }
    }
};

// Handles successful Google verification
function handleCredentialResponse(response) {
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("googleToken", response.credential);
    window.location.href = "/translator";
}

// Phone / OTP login handler
if ($("phone-login-form")) {
    $("phone-login-form").addEventListener("submit", (e) => {
        e.preventDefault();
        const phone = $("phone-number").value;
        alert(`OTP sent successfully to +91 ${phone}! (Simulated verification)`);
        localStorage.setItem("isLoggedIn", "true");
        localStorage.setItem("userPhone", phone);
        window.location.href = "/translator";
    });
}