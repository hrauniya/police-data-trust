interface InputValidation {
  errorMessageText: string,
  pattern: RegExp,
  inputType: string
}

export enum InputNames {
  FIRST_NAME = 'firstName',
  LAST_NAME = 'lastName',
  EMAIL_ADDRESS = 'emailAddress',
  PHONE_NUMBER = 'phoneNumber',
  CREATE_PASSWORD = 'createPassword',
  CONFIRM_PASSWORD = 'confirmPassword',
  LOGIN_PASSWORD = 'loginPassword'
}

const passwordRgx: RegExp = new RegExp("^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^a-zA-Z\d\s]).{8,}$")
const nameRgx: RegExp = new RegExp("^[' -]*[a-z]+[a-z' -]+$", 'i')

export const inputValidation: { [key in InputNames]: InputValidation } = {
  [InputNames.FIRST_NAME]: {
    errorMessageText: 'A first name is required',
    pattern: nameRgx,
    inputType: 'text'
  },
  [InputNames.LAST_NAME]: {
    errorMessageText: 'A last name is required',
    pattern: nameRgx,
    inputType: 'text'
  },
  [InputNames.EMAIL_ADDRESS]: {
    errorMessageText: 'Please enter a valid email address',
    pattern: new RegExp('^[a-z0-9_\.\-]+@([a-z0-9_\-]+\.)+[a-z]{2,4}$', 'i'),
    inputType: 'email'
  },
  [InputNames.PHONE_NUMBER]: {
    errorMessageText: 'Please enter a valid phone number',
    pattern: new RegExp('^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\s\.\/0-9]*$'),
    inputType: 'tel'
  },
  [InputNames.CREATE_PASSWORD]: {
    errorMessageText: 'Please enter a valid password',
    pattern: passwordRgx,
    inputType: 'password'
  },
  [InputNames.CONFIRM_PASSWORD]: {
    errorMessageText: 'Passwords do not match',
    pattern: passwordRgx,
    inputType: 'text'
  },
  [InputNames.LOGIN_PASSWORD]: {
    errorMessageText: 'A password is required',
    pattern: passwordRgx,
    inputType: 'password'
  }
}