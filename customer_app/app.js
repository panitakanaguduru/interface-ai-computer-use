document.addEventListener("DOMContentLoaded", () => {

    // =====================================================
    // STATE
    // =====================================================
  
    let activeMemberId = null;
    let conversationStarted = false;
  
    // =====================================================
    // ELEMENTS
    // =====================================================
  
    const welcomeScreen =
      document.getElementById("welcome-screen");
  
    const enterChat =
      document.getElementById("enter-chat");
  
    const welcomeAgent =
      document.getElementById("welcome-agent");
  
    const pupils =
      document.querySelectorAll(".pupil");
  
    const helloElements =
      document.querySelectorAll(".hello");
  
    const memberGate =
      document.getElementById("member-gate");
  
    const memberForm =
      document.getElementById("member-form");
  
    const memberInput =
      document.getElementById("customer-member-id");
  
    const memberContinue =
      document.getElementById("member-continue");
  
    const memberGateError =
      document.getElementById("member-gate-error");
  
    const chatApp =
      document.getElementById("chat-app");
  
    const startState =
      document.getElementById("start-state");
  
    const messages =
      document.getElementById("messages");
  
    const chatInput =
      document.getElementById("chat-input");
  
    const sendButton =
      document.getElementById("send-button");
  
    const homeButton =
      document.getElementById("home-button");
  
    const changingWord =
      document.getElementById("changing-word");
  
    const sessionLabel =
      document.getElementById("session-label");
  
  
    // =====================================================
    // HELPERS
    // =====================================================
  
    function wait(ms) {
      return new Promise(resolve => {
        setTimeout(resolve, ms);
      });
    }
  
  
    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }
  
  
    function scrollBottom() {
      setTimeout(() => {
        window.scrollTo({
          top: document.body.scrollHeight,
          behavior: "smooth"
        });
      }, 100);
    }
  
  
    function showMemberGate() {
  
      memberGate.classList.add("visible");
  
      memberGate.setAttribute(
        "aria-hidden",
        "false"
      );
  
      setTimeout(() => {
        memberInput.focus();
      }, 150);
    }
  
  
    function hideMemberGate() {
  
      memberGate.classList.remove(
        "visible"
      );
  
      memberGate.setAttribute(
        "aria-hidden",
        "true"
      );
    }
  
  
    function showChat() {
  
      chatApp.classList.add(
        "visible"
      );
  
      setTimeout(() => {
        chatInput.focus();
      }, 350);
    }
  
  
    // =====================================================
    // WELCOME AGENT EYES
    // =====================================================
  
    document.addEventListener(
      "mousemove",
      event => {
  
        if (
          welcomeScreen.classList.contains(
            "hidden"
          )
        ) {
          return;
        }
  
        const rect =
          welcomeAgent.getBoundingClientRect();
  
        const centerX =
          rect.left + rect.width / 2;
  
        const centerY =
          rect.top + rect.height / 2;
  
        const dx =
          event.clientX - centerX;
  
        const dy =
          event.clientY - centerY;
  
        const distance =
          Math.max(
            Math.sqrt(
              dx * dx + dy * dy
            ),
            1
          );
  
        const x =
          (dx / distance) * 5;
  
        const y =
          (dy / distance) * 5;
  
        pupils.forEach(pupil => {
  
          pupil.style.transform =
            `translate(${x}px, ${y}px)`;
  
        });
  
      }
    );
  
  
    // =====================================================
    // CHANGING WORD
    // =====================================================
  
    const words = [
      "your account.",
      "your spending.",
      "your claims.",
      "your activity."
    ];
  
    let wordIndex = 0;
  
    changingWord.style.transition =
      "opacity .2s ease, transform .2s ease";
  
    setInterval(() => {
  
      if (
        !chatApp.classList.contains(
          "visible"
        )
      ) {
        return;
      }
  
      wordIndex =
        (wordIndex + 1) %
        words.length;
  
      changingWord.style.opacity =
        "0";
  
      changingWord.style.transform =
        "translateY(5px)";
  
      setTimeout(() => {
  
        changingWord.textContent =
          words[wordIndex];
  
        changingWord.style.opacity =
          "1";
  
        changingWord.style.transform =
          "none";
  
      }, 220);
  
    }, 2600);
  
  
    // =====================================================
    // WELCOME → MEMBER IDENTIFICATION
    // =====================================================
  
    enterChat.addEventListener(
      "click",
      async () => {
  
        enterChat.disabled = true;
  
        helloElements.forEach(
          (hello, index) => {
  
            setTimeout(() => {
  
              hello.classList.add(
                "fade-away"
              );
  
            }, index * 35);
  
          }
        );
  
        await wait(400);
  
        welcomeScreen.classList.add(
          "exit"
        );
  
        await wait(600);
  
        welcomeScreen.classList.add(
          "hidden"
        );
  
        showMemberGate();
  
      }
    );
  
  
    // =====================================================
    // MEMBER LOGIN
    // =====================================================
  
    memberForm.addEventListener(
      "submit",
      async event => {
  
        event.preventDefault();
  
        const memberId =
          memberInput.value.trim();
  
        memberGateError.textContent =
          "";
  
        if (!memberId) {
  
          memberGateError.textContent =
            "Enter a demo member ID first.";
  
          return;
        }
  
        memberContinue.disabled =
          true;
  
        memberContinue.textContent =
          "checking...";
  
        try {
  
          // -----------------------------------------------
          // Verify member with backend
          // -----------------------------------------------
  
          const response =
            await fetch(
              `/api/member/${encodeURIComponent(memberId)}`
            );
  
          const data =
            await response.json();
  
          if (!response.ok) {
  
            throw new Error(
              data.error ||
              "We couldn't find that member."
            );
  
          }
  
          // -----------------------------------------------
          // Store the currently authenticated demo member
          // -----------------------------------------------
  
          activeMemberId =
            memberId;
  
          hideMemberGate();
  
          showChat();
  
          sessionLabel.textContent =
            `secure demo session • ${activeMemberId}`;
  
        }
        catch (error) {
  
          console.error(error);
  
          memberGateError.textContent =
            error.message ||
            "We couldn't find that member.";
  
        }
        finally {
  
          memberContinue.disabled =
            false;
  
          memberContinue.textContent =
            "continue →";
  
        }
  
      }
    );
  
  
    // =====================================================
    // START CONVERSATION
    // =====================================================
  
    function beginConversation() {
  
      if (
        conversationStarted
      ) {
        return;
      }
  
      conversationStarted = true;
  
      startState.classList.add(
        "hide-start"
      );
  
    }
  
  
    // =====================================================
    // USER MESSAGE
    // =====================================================
  
    function addUserMessage(text) {
  
      beginConversation();
  
      const wrapper =
        document.createElement(
          "div"
        );
  
      wrapper.className =
        "message user-message";
  
      wrapper.innerHTML = `
        <div class="user-label">
          YOU
        </div>
  
        <div class="user-bubble">
          ${escapeHtml(text)}
        </div>
      `;
  
      messages.appendChild(
        wrapper
      );
  
      scrollBottom();
  
    }
  
  
    // =====================================================
    // THINKING MESSAGE
    // =====================================================
  
    function addThinking(
      text =
        "looking through your account..."
    ) {
  
      const wrapper =
        document.createElement(
          "div"
        );
  
      wrapper.className =
        "message thinking-message";
  
      wrapper.innerHTML = `
        <div class="thinking-card">
  
          <div class="thinking-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
  
          <span>
            ${escapeHtml(text)}
          </span>
  
        </div>
      `;
  
      messages.appendChild(
        wrapper
      );
  
      scrollBottom();
  
      return wrapper;
  
    }
  
  
    // =====================================================
    // AGENT MESSAGE
    // =====================================================
  
    function addAgentMessage(text) {
  
      beginConversation();
  
      const wrapper =
        document.createElement(
          "div"
        );
  
      wrapper.className =
        "message agent-message";
  
      wrapper.innerHTML = `
        <div class="agent-message-top">
  
          <div class="response-agent">
            <span></span>
            <span></span>
          </div>
  
          <div class="agent-label">
            MEMBEROPS ✦
          </div>
  
        </div>
  
        <div class="agent-bubble">
  
          <div>
            ${escapeHtml(text)}
          </div>
  
        </div>
      `;
  
      messages.appendChild(
        wrapper
      );
  
      scrollBottom();
  
    }
  
  
    // =====================================================
    // ASK CUSTOMER AGENT
    // =====================================================
  
    async function ask(
      suppliedQuestion = null
    ) {
  
      const question =
        String(
          suppliedQuestion ??
          chatInput.value
        ).trim();
  
      if (!question) {
        return;
      }
  
      // ---------------------------------------------------
      // Customer must have an active member session
      // ---------------------------------------------------
  
      if (!activeMemberId) {
  
        addAgentMessage(
          "Your secure member session isn't active yet."
        );
  
        return;
      }
  
      // ---------------------------------------------------
      // Clear input
      // ---------------------------------------------------
  
      chatInput.value = "";
  
      autoResize();
  
      // ---------------------------------------------------
      // Show customer message
      // ---------------------------------------------------
  
      addUserMessage(
        question
      );
  
      sendButton.disabled =
        true;
  
      // ---------------------------------------------------
      // Thinking animation
      // ---------------------------------------------------
  
      const thinkingOptions = [
        "looking through your account...",
        "checking the paperwork...",
        "following the money...",
        "give me one tiny detective moment...",
        "finding the useful part..."
      ];
  
      const thinking =
        addThinking(
          thinkingOptions[
            Math.floor(
              Math.random() *
              thinkingOptions.length
            )
          ]
        );
  
      try {
  
        // =================================================
        // IMPORTANT
        //
        // We send BOTH:
        //
        // member_id
        // question
        //
        // The backend is responsible for enforcing
        // that the question cannot access another member.
        // =================================================
  
        const response =
          await fetch(
            "/api/customer/agent",
            {
              method: "POST",
  
              headers: {
                "Content-Type":
                  "application/json"
              },
  
              body: JSON.stringify({
                member_id:
                  activeMemberId,
  
                task:
                  question
              })
            }
          );
  
        const data =
          await response.json();
  
        // -------------------------------------------------
        // Remove thinking state
        // -------------------------------------------------
  
        thinking.remove();
  
        // -------------------------------------------------
        // Security block
        // -------------------------------------------------
  
        if (
          response.status === 403 &&
          data.blocked
        ) {
  
          addAgentMessage(
            data.error ||
            "I can only help with information associated with your current member session."
          );
  
          return;
        }
  
        // -------------------------------------------------
        // Other API errors
        // -------------------------------------------------
  
        if (!response.ok) {
  
          throw new Error(
            data.error ||
            "I couldn't complete that request."
          );
  
        }
  
        // -------------------------------------------------
        // Successful agent response
        // -------------------------------------------------
  
        addAgentMessage(
          data.answer ||
          "I finished checking your account."
        );
  
      }
      catch (error) {
  
        console.error(error);
  
        if (
          thinking &&
          thinking.isConnected
        ) {
          thinking.remove();
        }
  
        addAgentMessage(
          error.message ||
          "Something went wrong while I was checking your account."
        );
  
      }
      finally {
  
        sendButton.disabled =
          false;
  
        chatInput.focus();
  
      }
  
    }
  
  
    // =====================================================
    // SEND BUTTON
    // =====================================================
  
    sendButton.addEventListener(
      "click",
      () => {
        ask();
      }
    );
  
  
    // =====================================================
    // ENTER TO SEND
    // =====================================================
  
    chatInput.addEventListener(
      "keydown",
      event => {
  
        if (
          event.key === "Enter" &&
          !event.shiftKey
        ) {
  
          event.preventDefault();
  
          ask();
  
        }
  
      }
    );
  
  
    // =====================================================
    // SUGGESTION BUTTONS
    // =====================================================
  
    document
      .querySelectorAll(
        "[data-question]"
      )
      .forEach(button => {
  
        button.addEventListener(
          "click",
          () => {
  
            ask(
              button.dataset.question
            );
  
          }
        );
  
      });
  
  
    // =====================================================
    // HOME BUTTON
    // =====================================================
  
    homeButton.addEventListener(
      "click",
      () => {
  
        window.scrollTo({
          top: 0,
          behavior: "smooth"
        });
  
        chatInput.focus();
  
      }
    );
  
  
    // =====================================================
    // AUTO RESIZE
    // =====================================================
  
    function autoResize() {
  
      chatInput.style.height =
        "auto";
  
      chatInput.style.height =
        Math.min(
          chatInput.scrollHeight,
          130
        ) + "px";
  
    }
  
  
    chatInput.addEventListener(
      "input",
      autoResize
    );
  
  });