var client_name = null;
var latest_seen_message_id = null;  // used to check for changes
var oldest_message = null;  // id of currently oldest displayed message
var unclassified_messages = new Set();  // saved by id
var textarea = document.getElementById('chat_wrapper'); // used by auto scroll
var relabel_messages = true;  // Activate feature of dynamic message relabeling 

update_chat_log(true);  // update chat log and also the client name
setInterval(function(){update_chat_log(false)}, 1000);  // update chat log only

// ----- UPDATING THE CHAT LOG -----

function update_chat_log(full_update){
	// Synchronize the chat messages on screen with the ones in the server
	var dataToBeSent = { 
		// csrf token is necessary for django to not refuse the request
		csrfmiddlewaretoken: csrf_token, 
		type: (full_update) ? 'full_update' : 'update_chat_log',
		latest_seen_message_id: latest_seen_message_id,
		unclassified_messages: unclassified_messages_string(),
	};

	$.get('api/', dataToBeSent, function(data, textStatus) {
	    //data contains the JSON object from the server
        //console.log(data)  // Useful for debugging
		if (full_update){
			client_name = data.client_name
		}
		if (data.chat_log.length > 0){
			var new_latest_seen_message_id =
				data.chat_log[data.chat_log.length -1].message_id;
			if (new_latest_seen_message_id == latest_seen_message_id){
				return;  // Don't refresh if nothing has changed
			}
		}

		// Remember if user scrolled up the chat log to know if to autoscroll
		was_chat_scrolled_down = is_chat_scrolled_down();

		// --- ADD NEW MESSAGES TO CHATLOG ---
		add_new_messages_to_chat_log(data, full_update)

		// Scroll to bottom if new messages arrive and client didn't scroll up
		if (full_update || 
			(data.chat_log.length > 0 && was_chat_scrolled_down)){
            scroll_to_bottom();
		}

		// Set to remember last state of chat, so the server knows what we know
		if (data.chat_log.length > 0){
			latest_seen_message_id =
				data.chat_log[data.chat_log.length -1].message_id;  
		}

		// --- UPDATE CLASSIFICATION FOR UNCLASSIFIED MESSAGES ---
		update_new_classifications(data)

		// --- DELETE OLD MESSAGES FROM CHAT ---
		delete_old_messages(data)
	},"json");
}

function unclassified_messages_string(){
	// Create a string of the ids of unclassified messages,
    // that looks like python list. Can be easily interpreted by django server
	var unclassified_messages_as_string = '[';
	var unclassified_messages_array = Array.from(unclassified_messages);
	for (var i in unclassified_messages_array){
		unclassified_messages_as_string += unclassified_messages_array[i]+', ';
	}
	unclassified_messages_as_string += ']';
	return unclassified_messages_as_string;
}

function delete_old_messages(data){
	// Deletes messages from chat that are not saved on the server anymore
	if (data.oldest_message == null){
		// Delete every last message if no more messages exist on server
		$('#chat_wrapper').html('');
	}else if (oldest_message != null){
		// If messages in the client's chat exist, delete all too old ones
		while (oldest_message < data.oldest_message){
			$('#message_'+oldest_message).remove();
			oldest_message++;  // increment up to data's oldest message
		}
	}else{
		oldest_message = data.oldest_message;  // initial set
	}
}

function update_new_classifications(data){
    if (data.classified_messages == null) return;
    for (var message_id in data.classified_messages.single_classified){
        var classification = 
            data.classified_messages.single_classified[message_id];
        var classifications = 
            data.classified_messages.concatenated_classified[message_id];
        var previous_messages = 
            data.classified_messages.previous_messages[message_id];
        update_classification(message_id, classification,
                              classifications, previous_messages)
    }
}

function update_classification(message_id, classification,
                               classifications, previous_messages){
    // Relabel a message and/or previous messages based on new knowledge

    // Add tooltip about concatenated messages classes to the main message
    tooltip = compile_tooltip(message_id, classification, classifications,
                              previous_messages);
    $('#message_'+message_id).prop('title', tooltip);

    // Recolor and relabel the newly classified single message
    set_class(message_id, classification, null);
    unclassified_messages.delete(Number(message_id))
    console.log('Message with id', message_id, 'got classified as', 
                verbose_classification(classification));

    // Check if relabeling feature is active
    if (!($('#relabel_messages').is(":checked"))){return;}  

    // Relabel previous messages based on concatenation with the current message
    // For each concatenation ...
    for (var i=0; i<=previous_messages.length-1; i++){
        var concatenated_classification = classifications[i];

        // Avoid a reclassifictation in a !N N N secnario
        var last_concatenated = previous_messages[i];
        var last_concatenated_classification = get_class(last_concatenated);

        // For each message within the concatenation
        for (var j=0; j<=i; j++){
            var previous_message_id = previous_messages[j];
            previous_classification = get_class(previous_message_id)
            if (concatenated_classification != 'N'){ 
                if (previous_classification == 'N' 
                    && last_concatenated_classification == 'N'){

                    var comment = 'Relabeled due to ' + (i+2) 
                        + '-fold concatenation';
                    if (classification == 'N'){
                        set_class(
                            message_id, concatenated_classification, comment)
                        classification = concatenated_classification;
                    }
                    comment += ' of message ' + message_id;
                    set_class(previous_message_id,
                              concatenated_classification, comment)
                }
            }
        }
    }
}

function get_class(message_id){
    // get the class as a single capital letter from the div
    return $('#message_class_tag_'+message_id).text().split('[')[1].charAt(0);
}

function set_class(message_id, classification, comment){
    // (Re)label a message and appends the reason as a comment to the tooltip.

    current_class = get_class(message_id);
    new_tag = '[' + verbose_classification(classification) + ']';
    if (current_class != 'U' && current_class != classification){
        new_tag += '*';  // Means this messages has been relabeled
        append_to_tooltip(message_id, '\n\n' + comment);

        console.log('Message ' + message_id + ' relabeled from ' + 
            verbose_classification(current_class) + ' to ' + 
            verbose_classification(classification) + ': ' + comment);
    }
    $('#message_class_tag_'+message_id).html(new_tag);
    $('#message_'+message_id).removeClass('message_class_' + current_class);
    $('#message_'+message_id).addClass('message_class_' + classification);
}

function compile_tooltip(message_id, message_class, concatenated_classes,
                      previous_messages){
    /* Get the initial tooltip string for a message */

    tooltip = 'ID: ' + message_id +'\n\nOriginal Classification: ' + 
        verbose_classification(message_class) + 
        '\n\nConcatenated Classifications:\n';

    // Add concatenated messages ids + classification
    for (var i=previous_messages.length-1; i>-1; i--){
        s = '';
        for (var j=i; j>-1; j--){
            s += previous_messages[j] + '+';
        }
        tooltip += '\n' + s + message_id + ' -> ';
        if (concatenated_classes[i] == null){
            tooltip += verbose_classification('U');
        }else{
            tooltip += verbose_classification(concatenated_classes[i]);
        }
    }
    return tooltip;
}

function append_to_tooltip(message_id, string){
    // Append a string to the end of the tooltip of a message

    current = $('#message_'+message_id).prop('title');
    current = $('#message_'+message_id).prop('title', current + string);
}

function add_new_messages_to_chat_log(data, full_update){
	// Populate the chat log with new messages from server
	for (var i in data.chat_log){
        var chat_string = '';
		var message_class = data.chat_log[i].message_class;
		var time_stamp = to_client_time(data.chat_log[i].time_stamp);
		var author_name = data.chat_log[i].author_name;
		var right = (author_name == client_name)  // Push own messages right
		var message_string = data.chat_log[i].message_string;
		var message_id = data.chat_log[i].message_id;  
        var concatenated_classes = data.chat_log[i].concatenated_classes;
        var previous_messages = data.chat_log[i].previous_messages;
        var tooltip = compile_tooltip(message_id, message_class,
                                  concatenated_classes, previous_messages);
		chat_string += create_message_div(message_string, right, 
										  message_class, time_stamp,
										  author_name, message_id, tooltip);
        $('#chat_wrapper').append(chat_string);
		if (message_class == 'U'){
			unclassified_messages.add(message_id);
		}else if (full_update){
            // Also relabel based on wider context, if the page is (re)loaded
            update_classification(message_id, message_class,
                                  concatenated_classes, previous_messages)
        }
    }
}

function create_message_div(message_string, right, message_class, time_stamp,
							author_name, message_id, tooltip){
	var message_position = right ? 'right' : 'left';
	var message_position_anti = !right ? 'right' : 'left';
	var time_class = 'time_' + message_position;
    var message_id_class = 'message_id_' + message_position;
	// Avoid script injection
	var message_string = message_string.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;");
	return `
	<div id="message_${message_id}" class="message_container 
		message_class_${message_class} ${message_position}"
        data-toggle="tooltip" title="${tooltip}">
	  <img src="../static/chat/img/${author_name}.jpg"
          class="${message_position}" alt="${author_name}">
      <p class="chat_message">${message_string}</p>
      <div class="${time_class} grey"> ${time_stamp} </div>
      <div class="${message_id_class} grey"> ID:${message_id} </div>
      <div class="message_class_tag" id="message_class_tag_${message_id}">
          [${verbose_classification(message_class)}]
      </div>
	</div> 
	`; 
}

function verbose_classification(tag){
	switch(tag){
		case 'H': return 'HATESPEECH';
		case 'U': return 'UNCLASSIFIED';
		case 'O': return 'OFFENSIVE';
		case 'N': return 'NORMAL';
        default: return 'UNDEFINED class for invalid tag: ' + tag;
	}
}

// ----- POSTING CHAT MESSAGES -----

function post_message(){
	// csrf token is  necessary for django to not refuse the request
	var dataToBeSent = {csrfmiddlewaretoken: csrf_token,
						message: $('#message_field').val()}; 

	$.post('api/', dataToBeSent, function(data, textStatus) {
		// Update, also in case of race for first chat update and set_auth_name
		console.log('Posted a message as', data.client_name);
		client_name = data.client_name;  
	}, "json");

	// Make it look more responsive even with low update rates
    for (var i=1; i < 10; i++){
        setTimeout(function(){update_chat_log(false);}, i*50);
    }

	$('#message_field').val(''); // Delete the text field afterwards
    scroll_to_bottom();
}

$('#post_message').click(function() {
    // Post message on click of 'Send' Button
	post_message();  
});

$('#message_field').on('keyup', function(e) {
    if (e.keyCode == 13) {
		// Post message on press of 'Enter' key, when cursor in text field
		post_message();  
    }
});

$('#message_field').click(function() { 
	// autoscroll 11 times in one second to counter laggy soft keyboards
    scroll_to_bottom();
	for (var i=1; i <= 10; i++){
		setTimeout(
			function(){
                scroll_to_bottom();
            }, i*100
		)
	}
});

$('#relabel_messages').change(function(){
    $('#chat_wrapper').html('');
    relabel_messages = !relabel_messages;  // Activate feature of dynamic message relabeling 

    console.log('1')

    latest_seen_message_id = null;  // used to check for changes
    oldest_message = null;  // id of currently oldest displayed message
    update_chat_log(true);

    console.log('2')

});

// ----- GENERAL -----

function is_chat_scrolled_down(){
	// Check if the chat is scrolled almost (within 200px) all the way down
	if($('#chat_wrapper').scrollTop() + 
	   $('#chat_wrapper').innerHeight() >= 
	   $('#chat_wrapper')[0].scrollHeight - 200) {
		return true;
	}else{
		return false;
	}
}

function scroll_to_bottom(){
    var textarea = document.getElementById('chat_wrapper'); // used by auto scroll
    textarea.scrollTop = textarea.scrollHeight;  // autoscroll
}

function to_client_time(iso_date){
    unix_milli = new Date(iso_date).getTime() 
    var offset_milli = new Date().getTimezoneOffset()*60*1000;

    var date_client_side = new Date(unix_milli - offset_milli);
    const options = {hour: 'numeric', minute: 'numeric'}
    return date_client_side.toLocaleTimeString('de-de', options)
}
