import React from "react";
import { MDCButtonReact, MDCDialogReact } from "@orchest/lib-mdc";
import { RefManager } from "@orchest/lib-utils";

class AlertDialog extends React.Component {
  constructor() {
    super();

    this.refManager = new RefManager();
  }

  close() {
    this.refManager.refs.dialogRef.close();
  }

  render() {
    console.log("test");

    return (
      <MDCDialogReact
        ref={this.refManager.nrefs.dialogRef}
        title={this.props.title}
        onClose={this.props.onClose}
        content={this.props.content}
        actions={
          <MDCButtonReact
            classNames={["mdc-button--raised", "themed-secondary"]}
            submitButton
            label="Ok"
            onClick={this.close.bind(this)}
          />
        }
      />
    );
  }
}

export default AlertDialog;
