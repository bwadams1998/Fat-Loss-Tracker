{% extends "base.html" %}
{% block content %}
<section class="card">
  <h2>Your weekly split</h2>
  <div class="plan-grid">
    <div><strong>Day 1</strong><span>Push</span></div>
    <div><strong>Day 2</strong><span>Pull</span></div>
    <div><strong>Day 3</strong><span>Legs</span></div>
    <div><strong>Day 4</strong><span>Rest</span></div>
    <div><strong>Day 5</strong><span>Shoulders and Arms</span></div>
    <div><strong>Day 6</strong><span>Chest and Back</span></div>
    <div><strong>Day 7</strong><span>Rest</span></div>
  </div>
</section>
<section class="card">
  <h2>Cut rules</h2>
  <ul>
    <li>Start at 2300 calories daily.</li>
    <li>Hit 180 grams protein daily.</li>
    <li>Walk 8000 to 12000 steps daily.</li>
    <li>Lift 5 days per week.</li>
    <li>Add 20 to 40 minutes cardio, 3 to 5 days per week.</li>
    <li>If weight stalls for 2 weeks, lower calories by 150 to 200 or add 2000 steps.</li>
  </ul>
</section>
{% endblock %}
